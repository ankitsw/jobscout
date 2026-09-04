import json
from groq import AsyncGroq
from pydantic import BaseModel, Field, ValidationError
from app.config import settings

JUDGE_MODEL = "llama-3.3-70b-versatile"


class CVJudgement(BaseModel):
    relevance: int = Field(ge=1, le=5, description="Does the CV foreground the skills the JD asks for?")
    factuality: int = Field(ge=1, le=5, description="Is every claim traceable to the source resume? Any invented experience scores 1.")
    specificity: int = Field(ge=1, le=5, description="Concrete metrics and systems, not adjectives.")
    reasoning: str


_JUDGE_SYSTEM_PROMPT = """You are a strict evaluator of AI-generated resumes (CVs). You will be given the \
ORIGINAL RESUME (ground truth of what the candidate actually did), the JOB DESCRIPTION it was tailored for, \
and the GENERATED CV. Score the generated CV on three dimensions, each 1-5:

- relevance: count the core required skills/qualifications explicitly stated in the JOB DESCRIPTION (ignore "nice to have" \
sections). Score using these anchors, not a vibe: 1 = CV addresses none of the core requirements; 2 = CV addresses \
fewer than half; 3 = CV addresses most core requirements but misses the JD's primary domain or seniority level \
(e.g. JD wants 5+ years / a specific regulated domain / a specific specialization the resume doesn't have); \
4 = CV addresses all core requirements it can truthfully address and domain/seniority are a reasonable match; \
5 = CV addresses every core requirement AND domain AND seniority level stated in the JD with no gaps.
- factuality: mechanically list every named tool, language, framework, or technology that appears in the \
GENERATED CV's Skills section and Experience bullets. For EACH one, check whether that exact term appears \
anywhere in the ORIGINAL RESUME. A generated CV frequently adds a skill or technology from the job description \
into its Skills list (or into a rephrased bullet) that never appears in the original resume at all — this is \
invention, even if the rest of the CV is well-written and even if the added term seems like a plausible skill \
for someone with this background to have. ANY such term that appears in the generated CV but not in the original \
resume (in any form: skills list, bullets, project descriptions) means factuality must be scored 1. Do not give \
credit for "reasonable extrapolation" — the resume is the only source of truth, not what a candidate like this \
plausibly could also know. Moving a term that DOES appear somewhere in the original resume under a different \
section heading, or rephrasing a bullet's wording, is NOT invention — only score down for terms that are absent \
from the original resume entirely. Only score above 1 if you completed this term-by-term check and found no additions.
- specificity: does the CV use concrete metrics/systems/tools rather than vague adjectives ("results-driven", "team player")?

Reply with ONLY valid JSON: {"relevance": <int 1-5>, "factuality": <int 1-5>, "specificity": <int 1-5>, "reasoning": "<2-3 sentences, and for factuality name the specific added term if you found one>"}"""


def _build_user_prompt(original_resume: str, job_description: str, generated_cv: str) -> str:
    return (
        f"ORIGINAL RESUME:\n{original_resume}\n\n"
        f"JOB DESCRIPTION:\n{job_description}\n\n"
        f"GENERATED CV:\n{generated_cv}"
    )


async def judge_cv(original_resume: str, job_description: str, generated_cv: str) -> CVJudgement:
    client = AsyncGroq(api_key=settings.api_key)
    completion = await client.chat.completions.create(
        model=JUDGE_MODEL,
        max_tokens=400,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(original_resume, job_description, generated_cv)},
        ],
    )
    content = completion.choices[0].message.content
    if not content:
        raise ValueError("Empty response from judge model")
    content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return CVJudgement(**json.loads(content))
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Judge returned invalid output: {content!r}") from e
