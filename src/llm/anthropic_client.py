from __future__ import annotations

import json
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models import JobPosting, ProfileOverrides, TailoredResume
from src.scoring.ats_keywords import extract_jd_keywords
from src.settings import Settings


class ResumeGenerator:
    def __init__(self, settings: Settings, prompt_path: Path):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.request_timeout_seconds,
        )
        self.model = settings.openai_model
        self.prompt_template = prompt_path.read_text(encoding="utf-8")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=15))
    def generate(
        self,
        base_resume_text: str,
        job: JobPosting,
        candidate_name: str = "",
        profile: ProfileOverrides | None = None,
    ) -> TailoredResume:
        profile = profile or ProfileOverrides()
        user_prompt = self._build_user_prompt(base_resume_text, job, candidate_name, profile)

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,
            messages=[
                {"role": "system", "content": self.prompt_template},
                {"role": "user",   "content": user_prompt},
            ],
        )

        text = (response.choices[0].message.content or "").strip()
        data = _extract_json(text)
        return TailoredResume.model_validate(data)

    def _build_user_prompt(
        self,
        base_resume_text: str,
        job: JobPosting,
        candidate_name: str,
        profile: ProfileOverrides,
    ) -> str:
        # Extract every meaningful keyword token from the JD and present them
        # as an explicit must-mirror checklist — gives the LLM a concrete target.
        jd_keywords = extract_jd_keywords(job.text, min_len=4)
        keyword_checklist = ", ".join(jd_keywords)

        return f"""
Candidate preferred name: {candidate_name or profile.name}

Base resume:
{base_resume_text}

Optional profile overrides:
- Name: {profile.name}
- Email: {profile.email}
- Phone: {profile.phone}
- Location: {profile.location}
- LinkedIn: {profile.linkedin}
- Portfolio: {profile.portfolio}
- Summary override: {profile.summary_override}
- Preferred target roles: {', '.join(profile.target_roles)}
- Extra truthful keywords already in the candidate background: {', '.join(profile.extra_keywords)}

Target job metadata:
- URL: {job.url}
- Title: {job.title}
- Company: {job.company}
- Location: {job.location}

⚠ ATS KEYWORD CHECKLIST — every word below was extracted from the job description.
Your goal: use as many of these VERBATIM somewhere in the resume as truthfully possible.
Target coverage: 90%+ of these words must appear in the output.
{keyword_checklist}

Target job description:
{job.text}

Produce the strongest possible one-page ATS-friendly resume while remaining fully truthful.
Return JSON only.
""".strip()


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Model response did not contain JSON.\nResponse was:\n{text[:500]}")
    return json.loads(text[start : end + 1])
