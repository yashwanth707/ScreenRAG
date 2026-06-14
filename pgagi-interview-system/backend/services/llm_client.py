"""
ScreenRAG — Dual LLM Client (Ollama + Gemini Fallback)

Provides a unified interface for LLM text generation with automatic failover:
    1. Try Ollama (local, via HTTP API) first
    2. If Ollama fails (connection error, timeout, non-200), fall back to Gemini
    3. If both fail, raise HTTPException(503)

The fallback is SILENT to the user — only logged server-side.

Mirrors the VocalGauge pattern: httpx async client for Ollama,
google-generativeai SDK for Gemini, with JSON extraction utilities.

Usage:
    response = await generate("What is gradient descent?", system="You are a teacher.")
    parsed = extract_json_from_response(response)
"""

import json
import re
import logging
from typing import Optional

import httpx
from fastapi import HTTPException

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini client — lazy-initialized to avoid import-time API key errors
# ---------------------------------------------------------------------------
_gemini_model = None


def _get_gemini_model():
    """
    Lazily initialize the Gemini generative model.
    Only called when Ollama fails and we need the fallback.
    """
    global _gemini_model
    if _gemini_model is None:
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not configured. Set it in .env")
        
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("Gemini model initialized (gemini-2.5-flash)")
    return _gemini_model


# ---------------------------------------------------------------------------
# Ollama HTTP client
# ---------------------------------------------------------------------------
async def _generate_ollama(prompt: str, system: str = "") -> str:
    """
    Send a prompt to the Ollama API and return the response text.
    
    Args:
        prompt: The user prompt text.
        system: Optional system prompt for role/context setting.
    
    Returns:
        The LLM response text.
    
    Raises:
        Exception: On connection error, timeout, or non-200 status.
    """
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 8192,
            "temperature": 0.3,
        },
    }

    # Ollama supports system prompt via the 'system' field
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")


# ---------------------------------------------------------------------------
# Gemini SDK client
# ---------------------------------------------------------------------------
async def _generate_gemini(prompt: str, system: str = "") -> str:
    """
    Send a prompt to Google Gemini API and return the response text.
    
    Args:
        prompt: The user prompt text.
        system: Optional system prompt (prepended to the user prompt).
    
    Returns:
        The LLM response text.
    
    Raises:
        Exception: On API errors or missing configuration.
    """
    model = _get_gemini_model()
    
    # Gemini doesn't have a native system prompt in the basic API,
    # so we prepend it to the user prompt
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    # Use the synchronous API (Gemini SDK doesn't have native async)
    # This is fine because FastAPI runs this in a thread pool context
    response = model.generate_content(
        full_prompt,
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 4096,
        },
    )
    return response.text


# ---------------------------------------------------------------------------
# Unified generate function — Ollama first, Gemini fallback
# ---------------------------------------------------------------------------
async def generate(prompt: str, system: str = "") -> str:
    """
    Generate text using the LLM. Tries Ollama first, falls back to Gemini.
    
    The fallback is transparent to callers — they just get a response string.
    Which backend was used is only logged, never exposed to the user.
    
    Args:
        prompt: The user prompt text.
        system: Optional system prompt for context/role setting.
    
    Returns:
        The LLM response text.
    
    Raises:
        HTTPException(503): If BOTH backends fail.
    """
    # Attempt 1: Ollama (local)
    try:
        response = await _generate_ollama(prompt, system)
        if response.strip():
            logger.info("LLM response generated via Ollama")
            return response
        logger.warning("Ollama returned empty response, falling back to Gemini")
    except httpx.ConnectError:
        logger.warning("Ollama not reachable (ConnectError), falling back to Gemini")
    except httpx.TimeoutException:
        logger.warning("Ollama timed out, falling back to Gemini")
    except httpx.HTTPStatusError as e:
        logger.warning(f"Ollama returned HTTP {e.response.status_code}, falling back to Gemini")
    except Exception as e:
        logger.warning(f"Ollama failed ({type(e).__name__}: {e}), falling back to Gemini")

    # Attempt 2: Gemini (cloud fallback)
    try:
        response = await _generate_gemini(prompt, system)
        if response.strip():
            logger.info("LLM response generated via Gemini (fallback)")
            return response
        logger.error("Gemini returned empty response")
    except ValueError as e:
        logger.error(f"Gemini not configured: {e}")
    except Exception as e:
        logger.error(f"Gemini failed ({type(e).__name__}: {e})")

    # Both backends failed
    raise HTTPException(
        status_code=503,
        detail="Both LLM backends (Ollama and Gemini) are unavailable. "
               "Ensure Ollama is running or configure a valid GEMINI_API_KEY.",
    )


# ---------------------------------------------------------------------------
# JSON extraction utilities
# ---------------------------------------------------------------------------
def extract_json_from_response(raw: str) -> dict:
    """
    Safely extract a JSON object from LLM output.
    
    LLMs sometimes wrap JSON in markdown fences, add explanatory text,
    or include trailing content. This function strips all that away and
    finds the outermost JSON object.
    
    Args:
        raw: Raw text output from the LLM.
    
    Returns:
        Parsed JSON dictionary.
    
    Raises:
        json.JSONDecodeError: If no valid JSON can be extracted.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()

    # Find the outermost JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1

    if start == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found in LLM response", raw, 0)

    json_str = cleaned[start:end]
    return json.loads(json_str)


async def generate_json(prompt: str, system: str = "", retries: int = 1) -> dict:
    """
    Generate a JSON response from the LLM with automatic retry on parse failure.
    
    Combines generate() + extract_json_from_response() with retry logic.
    On first parse failure, retries with a stricter prompt asking for JSON only.
    
    Args:
        prompt: The user prompt text.
        system: Optional system prompt.
        retries: Number of retry attempts on parse failure.
    
    Returns:
        Parsed JSON dictionary from the LLM response.
    
    Raises:
        json.JSONDecodeError: If all attempts fail to produce valid JSON.
        HTTPException(503): If the LLM backends are unavailable.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1 + retries):
        try:
            if attempt == 0:
                raw = await generate(prompt, system)
            else:
                # Stricter retry prompt
                strict_system = (
                    "You MUST respond with ONLY a valid JSON object. "
                    "No markdown fences, no explanation, no preamble. "
                    "Start with { and end with }. Nothing else."
                )
                raw = await generate(prompt, f"{system}\n\n{strict_system}" if system else strict_system)

            return extract_json_from_response(raw)

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                f"LLM returned malformed JSON (attempt {attempt + 1}/{1 + retries}): {e}"
            )

    # All attempts exhausted
    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Health check for Ollama
# ---------------------------------------------------------------------------
async def check_ollama_health() -> dict:
    """
    Check if Ollama is reachable and the configured model is available.
    
    Returns:
        Health status dict with keys: reachable, model_available, models_list.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                model_available = any(settings.OLLAMA_MODEL in name for name in model_names)
                return {
                    "reachable": True,
                    "model_available": model_available,
                    "models_list": model_names,
                }
        return {"reachable": False, "model_available": False, "models_list": []}
    except Exception:
        return {"reachable": False, "model_available": False, "models_list": []}
