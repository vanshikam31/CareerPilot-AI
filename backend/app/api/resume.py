from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.database.session import get_db
from app.models.resume import Resume
from app.models.user import User, UserProfile
from app.schemas.resume import ResumeOut, ResumeUploadResponse
from app.schemas.user import ProfileOut
from app.services.pdf_reader import PDFError, extract_text
from app.services.resume_parser import merge_into_profile, parse_resume

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload", response_model=ResumeUploadResponse)
def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)  # never read more than the limit
    if len(data) > max_bytes:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")

    try:
        text = extract_text(data)
    except PDFError as exc:
        raise HTTPException(exc.status_code, str(exc))

    parsed, source = parse_resume(text)

    resume = Resume(
        user_id=user.id,
        filename=(file.filename or "resume.pdf")[:255],
        raw_text=text,
        parsed=parsed.model_dump(),
        source=source,
    )
    db.add(resume)

    if user.profile is None:
        user.profile = UserProfile()
    merge_into_profile(user.profile, parsed)

    db.commit()
    db.refresh(resume)
    db.refresh(user.profile)
    return ResumeUploadResponse(
        resume=ResumeOut.model_validate(resume),
        profile=ProfileOut.model_validate(user.profile),
    )


@router.get("/latest", response_model=ResumeOut)
def latest_resume(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = db.scalar(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.id.desc()).limit(1)
    )
    if resume is None:
        raise HTTPException(404, "No resume uploaded yet")
    return resume