from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.retrieval.search import SearchFilters, profile_query, search_jobs
from app.schemas.job import JobOut, SearchHitOut, SearchRequest

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

RESUME_QUERY_CHARS = 2000


@router.get("", response_model=list[JobOut])
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(select(Job).order_by(Job.id).limit(limit).offset(offset)).all()


@router.post("/search", response_model=list[SearchHitOut])
def search(
    req: SearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = SearchFilters(
        location=req.location,
        include_remote=req.include_remote,
        work_mode=req.work_mode,
        experience_level=req.experience_level,
    )
    return search_jobs(db, req.query, filters, mode=req.mode, limit=req.limit)


# NOTE: must be declared before "/{job_id}", otherwise "for-me" is parsed as an id.
@router.get("/for-me", response_model=list[SearchHitOut])
def jobs_for_me(
    source: Literal["profile", "resume"] = "profile",
    location: str | None = Query(None, max_length=100),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Basic personalised matches. Full ranking + explanations come in Phase 5."""
    if source == "resume":
        resume = db.scalar(
            select(Resume).where(Resume.user_id == user.id).order_by(Resume.id.desc()).limit(1)
        )
        if resume is None:
            raise HTTPException(404, "No resume uploaded yet")
        query, mode = resume.raw_text[:RESUME_QUERY_CHARS], "semantic"
    else:
        query, mode = profile_query(user.profile), "hybrid"
        if not query:
            raise HTTPException(400, "Add skills or target roles to your profile, or upload a resume first")

    return search_jobs(db, query, SearchFilters(location=location), mode=mode, limit=limit)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job