from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.user import ProfileOut


# NOTE: these three classes are also sent to Gemini as the response schema.
# They intentionally have no default values (Gemini's schema support is stricter).
class EducationItem(BaseModel):
    degree: str
    institution: str
    year: str


class ExperienceItem(BaseModel):
    title: str
    company: str
    duration: str
    description: str


class ResumeExtraction(BaseModel):
    full_name: str
    skills: list[str]
    education: list[EducationItem]
    experience: list[ExperienceItem]
    projects: list[str]
    experience_level: str  # fresher | junior | mid | senior | "" if unknown
    summary: str


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    source: str
    created_at: datetime
    parsed: ResumeExtraction


class ResumeUploadResponse(BaseModel):
    resume: ResumeOut
    profile: ProfileOut