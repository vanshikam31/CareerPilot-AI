from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WorkMode = Literal["onsite", "hybrid", "remote"]
Level = Literal["fresher", "junior", "mid", "senior"]
SearchMode = Literal["hybrid", "semantic", "keyword"]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    company: str
    location: str
    work_mode: str
    experience_level: str
    category: str
    skills: list[str]
    description: str


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    query: str = Field(min_length=2, max_length=500)
    location: str | None = Field(default=None, max_length=100)
    include_remote: bool = True  # when a location is given, still show remote jobs
    work_mode: WorkMode | None = None
    experience_level: Level | None = None
    mode: SearchMode = "hybrid"
    limit: int = Field(default=10, ge=1, le=50)


class SearchHitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job: JobOut
    score: float
    semantic_score: float
    keyword_score: float