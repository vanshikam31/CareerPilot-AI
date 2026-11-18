from fpdf import FPDF

from app.core.config import settings
from app.schemas.resume import EducationItem, ResumeExtraction
from app.services import resume_parser
from app.services.skill_catalog import extract_skills

RESUME_LINES = [
    "Aman Sharma",
    "aman@example.com",
    "B.Tech in Computer Science (AIML), 2026",
    "Skills: Python, SQL, FastAPI, PostgreSQL, Docker, scikit-learn, Java",
    "Projects: Built a RAG chatbot using LangChain and Gemini.",
    "Summer intern at ABC Technologies, built REST APIs.",
]


def make_pdf(lines: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "\n".join(lines))
    return bytes(pdf.output())


def upload(client, headers, content, name="cv.pdf", ctype="application/pdf"):
    return client.post(
        "/api/resume/upload", files={"file": (name, content, ctype)}, headers=headers
    )


# ---------- unit tests ----------
def test_extract_skills_word_boundaries():
    found = extract_skills("JavaScript, Node.js, C++, PostgreSQL, scikit-learn and sklearn.")
    for skill in ("JavaScript", "Node.js", "C++", "PostgreSQL"):
        assert skill in found
    assert "Java" not in found  # must not match inside JavaScript
    assert "SQL" not in found  # must not match inside PostgreSQL
    assert found.count("Scikit-learn") == 1  # alias + canonical -> one entry


def test_extract_skills_ignores_common_words():
    assert extract_skills("I excel at teamwork and can go the extra mile") == []


def test_fallback_parse_education_and_level():
    text = "Aman Sharma\nB.Tech in Computer Science, 2026\nSkills: Python, SQL\nSummer intern at XYZ"
    parsed, source = resume_parser.parse_resume(text)
    assert source == "fallback"
    assert parsed.full_name == "Aman Sharma"
    assert parsed.education[0].year == "2026"
    assert parsed.experience_level == "fresher"


# ---------- API tests ----------
def test_upload_requires_auth(client):
    r = client.post("/api/resume/upload", files={"file": ("cv.pdf", make_pdf(RESUME_LINES), "application/pdf")})
    assert r.status_code == 401


def test_upload_pdf_fills_profile(client, auth_headers):
    r = upload(client, auth_headers, make_pdf(RESUME_LINES))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resume"]["source"] == "fallback"
    skills = body["profile"]["skills"]
    for skill in ("Python", "SQL", "FastAPI", "PostgreSQL", "Docker", "Scikit-learn", "LangChain"):
        assert skill in skills
    assert body["profile"]["experience_level"] == "fresher"


def test_upload_does_not_overwrite_user_data(client, auth_headers):
    client.put(
        "/api/users/me/profile",
        json={"skills": ["Rust"], "education": "MIT", "experience_level": "junior"},
        headers=auth_headers,
    )
    upload(client, auth_headers, make_pdf(RESUME_LINES))
    profile = client.get("/api/users/me/profile", headers=auth_headers).json()
    assert profile["education"] == "MIT"
    assert profile["experience_level"] == "junior"
    assert "Rust" in profile["skills"] and "Python" in profile["skills"]


def test_upload_rejects_non_pdf(client, auth_headers):
    r = upload(client, auth_headers, b"just some text, not a pdf", name="cv.pdf")
    assert r.status_code == 415


def test_upload_rejects_pdf_without_text(client, auth_headers):
    r = upload(client, auth_headers, make_pdf(["Hi"]))
    assert r.status_code == 422


def test_gemini_failure_falls_back(client, auth_headers, monkeypatch):
    def boom(_text):
        raise RuntimeError("429 quota exceeded")

    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(resume_parser, "extract_with_gemini", boom)
    r = upload(client, auth_headers, make_pdf(RESUME_LINES))
    assert r.status_code == 200
    assert r.json()["resume"]["source"] == "fallback"
    assert "Python" in r.json()["profile"]["skills"]


def test_gemini_success_merges_with_keywords(client, auth_headers, monkeypatch):
    def fake(_text):
        return ResumeExtraction(
            full_name="Aman Sharma",
            skills=["Rust", "python"],
            education=[EducationItem(degree="B.Tech", institution="XYZ University", year="2026")],
            experience=[],
            projects=[],
            experience_level="Fresher",
            summary="AIML student",
        )

    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(resume_parser, "extract_with_gemini", fake)
    r = upload(client, auth_headers, make_pdf(RESUME_LINES))
    body = r.json()
    assert body["resume"]["source"] == "gemini"
    skills = body["profile"]["skills"]
    assert "Rust" in skills and "Python" in skills
    assert [s.lower() for s in skills].count("python") == 1  # case-insensitive dedupe
    assert body["profile"]["education"] == "B.Tech - XYZ University"
    assert body["profile"]["experience_level"] == "fresher"


def test_latest_resume(client, auth_headers):
    upload(client, auth_headers, make_pdf(RESUME_LINES))
    r = client.get("/api/resume/latest", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["filename"] == "cv.pdf"


def test_latest_resume_404(client, auth_headers):
    assert client.get("/api/resume/latest", headers=auth_headers).status_code == 404