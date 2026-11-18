from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=255)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _clean_list(values: list[str]) -> list[str]:
    seen, out = set(), []
    for v in values:
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


class ProfileUpdate(BaseModel):
    skills: list[str] = []
    target_roles: list[str] = []
    preferred_locations: list[str] = []
    experience_level: str | None = None
    education: str | None = None
    summary: str | None = None

    @field_validator("skills", "target_roles", "preferred_locations")
    @classmethod
    def clean(cls, v: list[str]) -> list[str]:
        return _clean_list(v)


class ProfileOut(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)