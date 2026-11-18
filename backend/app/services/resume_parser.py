import logging
import re

from app.core.config import settings
from app.models.user import UserProfile
from app.schemas.resume import EducationItem, ResumeExtraction
from app.services.gemini_extractor import extract_with_gemini
from app.services.skill_catalog import extract_skills

logger = logging.getLogger(__name__)

LEVELS = {"fresher", "junior", "mid", "senior"}
MAX_SKILLS = 60

_DEGREE_RE = re.compile(
    r"\b(?:b\.?\s?tech|m\.?\s?tech|bca|mca|bba|mba|b\.?\s?sc|m\.?\s?sc|b\.?\s?com"
    r"|ph\.?\s?d|bachelors? of|masters? of|diploma)\b|\b[bm]\.e\.",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_YEARS_EXP_RE = re.compile(
    r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?experience",
    re.IGNORECASE,
)


def merge_unique(first: list[str], second: list[str]) -> list[str]:
    seen, out = set(), []
    for item in [*first, *second]:
        item = item.strip()
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def _guess_level(text: str) -> str:
    years = [float(m) for m in _YEARS_EXP_RE.findall(text)]
    if years:
        y = max(years)
        return "fresher" if y < 1 else "junior" if y < 3 else "mid" if y < 6 else "senior"
    lower = text.lower()
    if any(word in lower for word in ("intern", "fresher", "student")):
        return "fresher"
    return ""


def _guess_name(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            ok = len(line) < 60 and "@" not in line and not any(c.isdigit() for c in line)
            return line if ok else ""
    return ""


def fallback_parse(text: str, skills: list[str]) -> ResumeExtraction:
    education = []
    for line in text.splitlines():
        line = line.strip()
        if 0 < len(line) < 150 and _DEGREE_RE.search(line):
            year = _YEAR_RE.findall(line)
            education.append(EducationItem(degree=line, institution="", year=year[-1] if year else ""))
        if len(education) == 3:
            break
    return ResumeExtraction(
        full_name=_guess_name(text),
        skills=skills,
        education=education,
        experience=[],  # honest: free-form experience needs the LLM
        projects=[],
        experience_level=_guess_level(text),
        summary="",
    )


def parse_resume(text: str) -> tuple[ResumeExtraction, str]:
    """Returns (parsed data, source) where source is 'gemini' or 'fallback'."""
    keyword_skills = extract_skills(text)

    if settings.gemini_api_key:
        try:
            data = extract_with_gemini(text)
            # Canonical keyword skills first so casing is consistent, then Gemini's extras.
            data.skills = merge_unique(keyword_skills, data.skills)[:MAX_SKILLS]
            level = data.experience_level.strip().lower()
            data.experience_level = level if level in LEVELS else _guess_level(text)
            return data, "gemini"
        except Exception as exc:  # quota, timeout, bad JSON, wrong model name...
            logger.warning("Gemini extraction failed, using fallback: %s", exc)

    return fallback_parse(text, keyword_skills[:MAX_SKILLS]), "fallback"


def merge_into_profile(profile: UserProfile, parsed: ResumeExtraction) -> None:
    """Fill the profile from the resume WITHOUT overwriting what the user typed."""
    profile.skills = merge_unique(list(profile.skills or []), parsed.skills)
    if not profile.experience_level and parsed.experience_level:
        profile.experience_level = parsed.experience_level
    if not profile.education and parsed.education:
        top = parsed.education[0]
        text = f"{top.degree} - {top.institution}" if top.institution else top.degree
        profile.education = text[:255]
    if not profile.summary and parsed.summary:
        profile.summary = parsed.summary