"""
Extracts structured information from PDF resumes using pdfplumber and the LLM.
"""

import logging
from typing import Any

import pdfplumber

from services.llm_client import generate_json

logger = logging.getLogger(__name__)


# LLM prompt for structured resume extraction
RESUME_EXTRACTION_PROMPT = """Analyze the following resume text and extract structured information.

Resume Text:
{resume_text}

Return ONLY a valid JSON object with these exact fields:
{{
    "name": "<candidate's full name>",
    "skills": ["<skill1>", "<skill2>", "..."],
    "technologies": ["<tech1>", "<tech2>", "..."],
    "projects_summary": "<2-3 sentence summary of key projects>",
    "experience_level": "<junior|mid|senior>",
    "education": "<highest education level and field>"
}}

Rules:
- "skills" should include both technical and relevant soft skills
- "technologies" should include programming languages, frameworks, tools, platforms
- "experience_level" should be inferred from years of experience, role titles, and project complexity:
  - "junior": 0-2 years or student/intern/entry-level roles
  - "mid": 2-5 years or mid-level roles with moderate project complexity
  - "senior": 5+ years or senior/lead/principal roles with complex projects
- If the name cannot be determined, use "Unknown Candidate"
- Keep the projects_summary concise but informative
- Do NOT include explanations or markdown — JSON only"""


RESUME_EXTRACTION_SYSTEM = (
    "You are an expert HR resume analyzer. Extract structured information "
    "from resumes accurately. Always respond with valid JSON only."
)


# PDF text extraction
def _extract_text_from_pdf(file_path: str) -> str:
    """Extract all text content from a PDF file using pdfplumber."""
    pages_text = []
    
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text()
                if text and text.strip():
                    pages_text.append(text.strip())
            except Exception as e:
                logger.warning(f"Failed to extract text from page {i + 1}: {e}")
                continue

    full_text = "\n\n".join(pages_text)
    logger.info(f"Extracted {len(full_text)} chars from {len(pages_text)} pages: {file_path}")
    return full_text


# Main resume parsing function
async def parse_resume_pdf(file_path: str) -> dict[str, Any]:
    """Parse a PDF resume into structured data."""
    raw_text = _extract_text_from_pdf(file_path)
    
    if not raw_text.strip():
        raise ValueError(
            "No text could be extracted from the PDF. "
            "The file may be scanned/image-based or corrupted."
        )

    truncated_text = raw_text[:6000] if len(raw_text) > 6000 else raw_text

    prompt = RESUME_EXTRACTION_PROMPT.format(resume_text=truncated_text)
    
    try:
        parsed = await generate_json(prompt, system=RESUME_EXTRACTION_SYSTEM, retries=1)
        
        # Validate and normalize the response
        result = {
            "name": parsed.get("name", "Unknown Candidate"),
            "raw_text": raw_text,
            "skills": _ensure_list(parsed.get("skills", [])),
            "technologies": _ensure_list(parsed.get("technologies", [])),
            "projects_summary": parsed.get("projects_summary", "No projects found"),
            "experience_level": _normalize_experience_level(
                parsed.get("experience_level", "mid")
            ),
            "education": parsed.get("education", "Not specified"),
        }
        
        logger.info(
            f"Resume parsed: name={result['name']}, "
            f"skills={len(result['skills'])}, "
            f"experience={result['experience_level']}"
        )
        return result

    except Exception as e:
        logger.error(f"LLM resume extraction failed: {e}")
        # Return a basic fallback with just the raw text
        return {
            "name": "Unknown Candidate",
            "raw_text": raw_text,
            "skills": _extract_basic_skills(raw_text),
            "technologies": [],
            "projects_summary": "Resume text extracted but structured parsing failed.",
            "experience_level": "mid",
            "education": "Not determined",
        }


# Helper functions
def _ensure_list(value: Any) -> list[str]:
    """Ensure a value is a list of strings."""
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        return [value]
    return []


def _normalize_experience_level(level: str) -> str:
    """Normalize experience level to one of: junior, mid, senior."""
    level = level.lower().strip()
    if level in ("junior", "entry", "intern", "fresher", "beginner"):
        return "junior"
    if level in ("senior", "lead", "principal", "staff", "expert"):
        return "senior"
    return "mid"


def _extract_basic_skills(text: str) -> list[str]:
    """
    Fallback skill extraction using keyword matching.
    Used when LLM parsing fails.
    """
    common_skills = [
        "python", "java", "javascript", "typescript", "c++", "go", "rust",
        "react", "node.js", "django", "flask", "fastapi", "spring",
        "sql", "postgresql", "mongodb", "redis", "elasticsearch",
        "docker", "kubernetes", "aws", "gcp", "azure",
        "machine learning", "deep learning", "nlp", "computer vision",
        "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
        "git", "linux", "rest api", "graphql", "microservices",
    ]
    
    text_lower = text.lower()
    found = [skill for skill in common_skills if skill in text_lower]
    return found[:15]  # Cap at 15 skills
