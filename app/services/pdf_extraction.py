import io
import re

import pdfplumber
import wordninja

# pdfplumber renders a glyph it can't map to Unicode (common with icon fonts
# resume templates use for phone/email/link symbols) as a literal "(cid:N)"
# token in the extracted text instead of silently dropping it.
_CID_NOISE_RE = re.compile(r"\(cid:\d+\)\s*")

# Real English words - even long technical/compound ones - essentially never
# exceed this many characters. A PDF where words got extracted with no space
# between them (some fonts/generators lay out text as individually
# positioned glyphs, or genuinely omit space characters and rely on tiny
# horizontal gaps pdfplumber's word-break heuristic can miss) produces runs
# like "Workedasadatascientistbuild" instead.
_MERGED_WORD_LENGTH = 20
_MERGED_WORD_RATIO = 0.05

# Contact-info lines (email|phone|linkedin|github, all pipe- or
# slash-joined with no spaces) are exactly as long and space-free as a
# genuinely merged sentence, but running them through English word
# segmentation destroys the actual data (an email becomes "an kits he
# rawat 001 gmail com"). Never touch a token that looks like it carries
# structured data rather than prose.
_STRUCTURED_TOKEN_RE = re.compile(r"[@/:]|\d{3,}")


def _looks_garbled(text: str) -> bool:
    words = text.split()
    if not words:
        return False
    long_words = sum(1 for w in words if len(w) > _MERGED_WORD_LENGTH)
    return (long_words / len(words)) > _MERGED_WORD_RATIO


def _extract(pdf: pdfplumber.PDF, **kwargs) -> str:
    return "\n".join(page.extract_text(**kwargs) or "" for page in pdf.pages)


def _degarble_line(line: str) -> str:
    words = []
    for word in line.split():
        if len(word) > _MERGED_WORD_LENGTH and not _STRUCTURED_TOKEN_RE.search(word):
            # English word-frequency segmentation - not perfect on proper
            # nouns/acronyms ("IIT" -> "I IT"), but far more usable than one
            # unreadable N-character blob feeding straight into an LLM.
            words.extend(wordninja.split(word))
        else:
            words.append(word)
    return " ".join(words)


def extract_resume_text(pdf_bytes: bytes) -> str:
    """Extract text from an uploaded resume PDF, working around real
    pdfplumber failure modes seen on production uploads rather than trusting
    the default extraction blindly."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = _extract(pdf)
        if _looks_garbled(text):
            # A tighter x_tolerance catches smaller character gaps as word
            # boundaries - fixes some merged-word cases at the cost of
            # occasionally over-splitting a normal word.
            tighter = _extract(pdf, x_tolerance=1)
            if not _looks_garbled(tighter):
                text = tighter

    text = _CID_NOISE_RE.sub("", text).strip()

    if _looks_garbled(text):
        # The gap was too small for any tolerance setting to recover
        # (some PDF generators emit essentially zero space between words) -
        # segment the merged runs directly instead of shipping unreadable text.
        text = "\n".join(_degarble_line(line) for line in text.split("\n"))

    return text
