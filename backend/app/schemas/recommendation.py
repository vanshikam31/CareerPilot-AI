from pydantic import BaseModel, ConfigDict

from app.schemas.job import JobOut


class ScoreBreakdown(BaseModel):
    semantic: float
    skills: float
    role: float
    level: float
    location: float


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job: JobOut
    score: float
    breakdown: ScoreBreakdown
    matched_skills: list[str]
    missing_skills: list[str]
    reasons: list[str]


class LearningItem(BaseModel):
    skill: str
    jobs_needing_it: int
    percent_of_top_jobs: int


class LearningPathOut(BaseModel):
    based_on_jobs: int
    skills: list[LearningItem]


class SkillGapOut(BaseModel):
    job: JobOut
    matched: list[str]
    missing: list[str]
    match_percent: int