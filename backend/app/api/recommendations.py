from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.job import Job
from app.models.user import User
from app.recommendations.ranker import skill_match
from app.recommendations.service import NoProfileError, learning_path, recommend_for_user
from app.schemas.job import JobOut
from app.schemas.recommendation import LearningPathOut, RecommendationOut, SkillGapOut

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendationOut])
def recommendations(
    location: str | None = Query(None, max_length=100),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Personalised ranking with a score breakdown and reasons for every job."""
    try:
        return recommend_for_user(db, user, location=location, limit=limit)
    except NoProfileError as exc:
        raise HTTPException(400, str(exc))


@router.get("/learning-path", response_model=LearningPathOut)
def learning(
    top_jobs: int = Query(10, ge=3, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        recs = recommend_for_user(db, user, limit=top_jobs)
    except NoProfileError as exc:
        raise HTTPException(400, str(exc))
    return LearningPathOut(based_on_jobs=len(recs), skills=learning_path(recs))


@router.get("/skill-gap/{job_id}", response_model=SkillGapOut)
def skill_gap(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    mine = user.profile.skills if user.profile else []
    score, matched, missing = skill_match(mine, job.skills)
    return SkillGapOut(
        job=JobOut.model_validate(job), matched=matched, missing=missing, match_percent=round(score * 100)
    )