"""
Generates personalized interview questions based on candidate profile,
RAG context, and previous Q&A history.
"""

import logging
from typing import Any

from services.llm_client import generate_json
from services.rag_engine import retrieve_context

logger = logging.getLogger(__name__)


# Role display names
ROLE_DISPLAY = {
    "ai_ml": "AI/ML Engineer",
    "backend": "Backend Engineer",
    "data_science": "Data Scientist",
}

# Topic pools per role
ROLE_TOPICS = {
    "ai_ml": [
        "supervised_learning", "unsupervised_learning", "neural_networks",
        "deep_learning", "optimization", "regularization", "model_evaluation",
        "feature_engineering", "nlp", "computer_vision", "reinforcement_learning",
        "ensemble_methods", "dimensionality_reduction", "transfer_learning",
    ],
    "backend": [
        "system_design", "databases", "api_design", "caching",
        "concurrency", "distributed_systems", "security", "testing",
        "microservices", "message_queues", "load_balancing", "monitoring",
    ],
    "data_science": [
        "statistics", "probability", "hypothesis_testing", "regression",
        "classification", "clustering", "data_visualization", "feature_selection",
        "time_series", "experimental_design", "bayesian_methods", "model_deployment",
    ],
}


# LLM prompt
QUESTION_GENERATION_PROMPT = """You are a technical interviewer for a {role_display} position.

You have retrieved the following reference material from technical textbooks:
---
{retrieved_chunks}
---

Candidate Profile:
- Skills: {skills}
- Experience Level: {experience_level}
- This is question {question_num} of {max_questions}

Previous questions asked (DO NOT repeat these topics):
{previous_topics}

{difficulty_instruction}

Generate ONE specific, thoughtful interview question that:
- Is directly grounded in the retrieved reference material above
- Matches the candidate's experience level ({experience_level})
- Has NOT been asked before (avoid topics: {previous_topics})
- Tests conceptual understanding, not just definitions
- Is phrased conversationally, as a real interviewer would ask
- For {experience_level} candidates, adjust complexity accordingly

Respond ONLY with JSON:
{{"question": "<your interview question>", "topic": "<topic_area>", "difficulty": "<basic|intermediate|advanced>"}}"""


QUESTION_SYSTEM_PROMPT = (
    "You are an expert technical interviewer. Generate questions that are "
    "insightful, specific, and grounded in the provided reference material. "
    "Always respond with valid JSON only — no markdown, no explanation."
)


# Adaptive difficulty logic
def _determine_difficulty(
    experience_level: str,
    previous_qa: list[dict],
    question_num: int,
) -> str:
    """Determine difficulty for the next question based on experience level and past answers."""
    # Baseline from experience level
    baseline_map = {
        "junior": "basic",
        "mid": "intermediate",
        "senior": "advanced",
    }
    baseline = baseline_map.get(experience_level, "intermediate")
    difficulty_levels = ["basic", "intermediate", "advanced"]
    current_idx = difficulty_levels.index(baseline)

    # Adaptive: check last answer length
    if previous_qa:
        last_answer = previous_qa[-1].get("answer", "")
        word_count = len(last_answer.split()) if last_answer else 0

        if word_count < 30:
            # Short answer → lower difficulty
            current_idx = max(0, current_idx - 1)
            logger.info(f"Adaptive: short answer ({word_count} words) → lowering difficulty")
        elif word_count > 150:
            # Detailed answer → raise difficulty
            current_idx = min(2, current_idx + 1)
            logger.info(f"Adaptive: detailed answer ({word_count} words) → raising difficulty")

    # Question progression: later questions tend harder
    if question_num >= 5:
        current_idx = min(2, current_idx + 1)
    elif question_num <= 2:
        current_idx = max(0, current_idx)

    return difficulty_levels[current_idx]


def _get_difficulty_instruction(difficulty: str, experience_level: str) -> str:
    """Build a difficulty instruction for the LLM prompt."""
    instructions = {
        "basic": (
            "Generate a BASIC level question. It should test fundamental concepts "
            "and definitions. Suitable for someone getting started."
        ),
        "intermediate": (
            "Generate an INTERMEDIATE level question. It should require applying "
            "concepts to scenarios, comparing approaches, or explaining trade-offs."
        ),
        "advanced": (
            "Generate an ADVANCED level question. It should require deep understanding, "
            "system design thinking, or solving complex edge cases."
        ),
    }
    return instructions.get(difficulty, instructions["intermediate"])


# Topic tracking
def _get_covered_topics(previous_qa: list[dict]) -> list[str]:
    """Extract topics already covered from previous Q&A pairs."""
    topics = []
    for qa in previous_qa:
        topic = qa.get("topic", "")
        if topic:
            topics.append(topic)
    return topics


def _build_retrieval_query(
    skills: list[str],
    role: str,
    covered_topics: list[str],
    question_num: int,
) -> str:
    """
    Build a retrieval query that combines:
        - Candidate skills
        - Role-specific topic areas not yet covered
        - Progression context
    """
    # Get uncovered topics for this role
    all_topics = ROLE_TOPICS.get(role, [])
    uncovered = [t for t in all_topics if t not in covered_topics]
    
    # Pick a target topic area (cycle through uncovered topics)
    if uncovered:
        target_topic = uncovered[question_num % len(uncovered)]
    else:
        # All topics covered — re-use with deeper focus
        target_topic = all_topics[question_num % len(all_topics)] if all_topics else ""

    # Combine skills + target topic into a retrieval query
    skill_str = ", ".join(skills[:5]) if skills else "general programming"
    query = f"{target_topic.replace('_', ' ')} {skill_str} {ROLE_DISPLAY.get(role, role)}"
    
    return query


# Main generation function
async def generate_question(
    session_data: dict[str, Any],
    previous_qa: list[dict],
    question_num: int,
    max_questions: int = 7,
) -> dict[str, Any]:
    """Generate a personalized interview question."""
    role = session_data.get("role", "ai_ml")
    skills = session_data.get("skills", [])
    experience_level = session_data.get("experience_level", "mid")

    difficulty = _determine_difficulty(experience_level, previous_qa, question_num)
    
    covered_topics = _get_covered_topics(previous_qa)
    retrieval_query = _build_retrieval_query(skills, role, covered_topics, question_num)

    retrieved_chunks = retrieve_context(retrieval_query, role, n_results=5)
    chunks_text = "\n\n".join(retrieved_chunks) if retrieved_chunks else (
        "No reference material available. Generate a question based on general "
        f"knowledge for a {ROLE_DISPLAY.get(role, role)} position."
    )

    previous_topics_str = ", ".join(covered_topics) if covered_topics else "None (this is the first question)"
    difficulty_instruction = _get_difficulty_instruction(difficulty, experience_level)

    prompt = QUESTION_GENERATION_PROMPT.format(
        role_display=ROLE_DISPLAY.get(role, role),
        retrieved_chunks=chunks_text,
        skills=", ".join(skills) if skills else "Not specified",
        experience_level=experience_level,
        question_num=question_num,
        max_questions=max_questions,
        previous_topics=previous_topics_str,
        difficulty_instruction=difficulty_instruction,
    )

    try:
        parsed = await generate_json(prompt, system=QUESTION_SYSTEM_PROMPT, retries=1)

        result = {
            "question_text": parsed.get("question", "Tell me about your experience."),
            "topic": parsed.get("topic", "general"),
            "difficulty": parsed.get("difficulty", difficulty),
            "rag_context": chunks_text[:2000],  # Store truncated for DB
        }

        logger.info(
            f"Generated Q{question_num}: topic={result['topic']}, "
            f"difficulty={result['difficulty']}"
        )
        return result

    except Exception as e:
        logger.error(f"Question generation failed: {e}")
        # Fallback question
        role_display = ROLE_DISPLAY.get(role, role)
        return {
            "question_text": (
                f"Based on your experience as a {role_display}, "
                f"can you walk me through a challenging project you've worked on "
                f"and the technical decisions you made?"
            ),
            "topic": "experience",
            "difficulty": difficulty,
            "rag_context": "",
        }
