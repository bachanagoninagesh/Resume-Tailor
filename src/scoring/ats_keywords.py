from __future__ import annotations

import re


# Common English stop-words to exclude from keyword matching
STOP_WORDS: frozenset[str] = frozenset({
    "the", "and", "for", "are", "with", "this", "that", "have", "will",
    "from", "they", "been", "their", "has", "was", "were", "you", "your",
    "our", "not", "but", "can", "all", "any", "may", "use", "used", "using",
    "also", "such", "than", "each", "more", "other", "both", "its", "into",
    "able", "well", "when", "who", "how", "what", "which", "within", "across",
    "work", "team", "role", "help", "strong", "good", "including", "experience",
    "provide", "ensure", "support", "make", "must", "required", "preferred",
    "ability", "skills", "position", "candidate", "apply", "opportunity",
    "working", "related", "relevant", "responsibilities", "requirements",
})


def tokenize_set(text: str) -> set[str]:
    """Lowercase alphabetic tokens (length >= 3) minus stop-words."""
    return {w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP_WORDS}


def extract_jd_keywords(jd_text: str, min_len: int = 4) -> list[str]:
    """
    Return sorted list of meaningful keywords from a job description.
    Used to build the explicit must-use checklist for the LLM.
    """
    return sorted(t for t in tokenize_set(jd_text) if len(t) >= min_len)


def overlap_score(resume_text: str, job_text: str) -> tuple[float, list[str]]:
    """
    Returns (score 0-1, list of matched keywords).
    Score = fraction of unique job keywords found in resume text.
    """
    job_tokens = tokenize_set(job_text)
    res_tokens = tokenize_set(resume_text)

    if not job_tokens:
        return 0.0, []

    matched = sorted(job_tokens & res_tokens)
    score   = len(matched) / len(job_tokens)
    return score, matched
