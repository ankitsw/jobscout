from groq import AsyncGroq
from app.config import settings

MODEL = "meta-llama/llama-prompt-guard-2-86m"
flag_threshold = 0.5

_MAX_CHARS = 1000


async def is_likely_injection(text: str) -> bool:
    """
    Uses a Groq model to determine if the given text is likely to be an injection attempt.
    Returns True if the text is likely an injection, False otherwise.
    """
    if not text:
        return False
    client = AsyncGroq(api_key=settings.api_key)
    sample = text if len(text) <= _MAX_CHARS else text[:_MAX_CHARS] + " ... " + text[-_MAX_CHARS:]
    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": sample}],
        max_tokens=8,
    )
    content = resp.choices[0].message.content or ""
    try: 
        score = float(content)
    except (ValueError, TypeError):
        return False
    
    return score >= flag_threshold
