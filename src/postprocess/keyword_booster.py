"""
Keyword Booster — post-generation ATS gap closer.

After the LLM generates the resume JSON and the optimizer cleans it, this
module closes the remaining ATS gap without fabricating anything:

  1. Computes which JD keyword-tokens are still missing from the resume output.
  2. Checks each missing token against the candidate's truthful background
     (base resume text + profile.extra_keywords + profile.target_roles).
  3. Appends every confirmed-truthful token to ats_keywords_used, which is
     included in the ATS scoring pass.

No employers, dates, metrics, tools, or skills are invented — only existing
keywords that the LLM happened to omit are bridged in.
"""
from __future__ import annotations

from src.models import ProfileOverrides, TailoredResume
from src.scoring.ats_keywords import tokenize_set


def _resume_to_text(r: TailoredResume) -> str:
    """Flatten every text field of the tailored resume into one string."""
    parts: list[str] = [
        r.target_title,
        r.summary,
        " ".join(r.skills),
        " ".join(r.certifications),
        " ".join(r.ats_keywords_used),
        " ".join(f"{e.title} {e.company}" for e in r.experience),
        " ".join(b for e in r.experience for b in e.bullets),
        " ".join(s.name for e in r.experience for s in e.sections if s.name),
        " ".join(b for e in r.experience for s in e.sections for b in s.bullets),
        " ".join(
            f"{e.degree} {e.school} {e.details} {e.coursework}"
            for e in r.education
        ),
    ]
    return "\n".join(p for p in parts if p)


def boost_keywords(
    resume: TailoredResume,
    jd_text: str,
    base_resume_text: str,
    profile: ProfileOverrides,
) -> TailoredResume:
    """
    Inject JD keywords that are missing from the resume but truthfully
    present in the candidate's background into ats_keywords_used.

    Returns the (mutated) resume with an expanded ats_keywords_used list.
    """
    # --- What is currently in the generated resume output ---
    resume_tokens = tokenize_set(_resume_to_text(resume))

    # --- What the JD actually requires ---
    jd_tokens = tokenize_set(jd_text)

    # --- Everything the candidate truthfully has ---
    candidate_text = " ".join(filter(None, [
        base_resume_text,
        " ".join(profile.extra_keywords),
        " ".join(profile.target_roles),
        profile.summary_override,
    ]))
    candidate_tokens = tokenize_set(candidate_text)

    # --- Gap: in JD but not yet in resume, AND truthfully in candidate bg ---
    missing = jd_tokens - resume_tokens
    injectable = sorted(
        t for t in missing
        if t in candidate_tokens and len(t) >= 4
    )

    # --- Append without duplicates ---
    existing_lower = {w.lower() for w in resume.ats_keywords_used}
    for kw in injectable:
        if kw not in existing_lower:
            resume.ats_keywords_used.append(kw)
            existing_lower.add(kw)

    return resume
