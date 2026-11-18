from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.user import User, UserProfile
from app.schemas.user import ProfileOut, ProfileUpdate, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user)):
    return user.profile


@router.put("/me/profile", response_model=ProfileOut)
def update_profile(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile: UserProfile = user.profile
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile