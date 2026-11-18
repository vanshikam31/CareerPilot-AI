import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.services import embeddings

WORK_MODES = {"onsite", "hybrid", "remote"}
LEVELS = {"fresher", "junior", "mid", "senior"}
REQUIRED = ("title", "company", "location", "work_mode", "experience_level", "category", "skills", "description")


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def job_text(row: dict) -> str:
    """The text that gets embedded. Location is left out on purpose (handled by filters)."""
    return f"{row['title']}. {row['category']}. Skills: {', '.join(row['skills'])}. {row['description']}"


def _validate(row: dict, n: int) -> dict:
    missing = [k for k in REQUIRED if k not in row or row[k] in (None, "", [])]
    if missing:
        raise ValueError(f"Row {n}: missing {missing}")
    skills = row["skills"]
    if isinstance(skills, str):
        skills = skills.split("|")
    clean = {k: row[k].strip() for k in REQUIRED if k != "skills"}
    clean["skills"] = [s.strip() for s in skills if s.strip()]
    clean["work_mode"] = clean["work_mode"].lower()
    clean["experience_level"] = clean["experience_level"].lower()
    if clean["work_mode"] not in WORK_MODES:
        raise ValueError(f"Row {n}: invalid work_mode '{clean['work_mode']}'")
    if clean["experience_level"] not in LEVELS:
        raise ValueError(f"Row {n}: invalid experience_level '{clean['experience_level']}'")
    return clean


def ingest_rows(db: Session, rows: list[dict], batch_size: int = 32) -> tuple[int, int]:
    """Embeds and stores jobs. Safe to run again: existing jobs are skipped.
    Returns (added, skipped)."""
    existing = {
        (t.lower(), c.lower(), l.lower())
        for t, c, l in db.execute(select(Job.title, Job.company, Job.location))
    }
    fresh, skipped = [], 0
    for n, raw in enumerate(rows, start=1):
        row = _validate(raw, n)
        key = (row["title"].lower(), row["company"].lower(), row["location"].lower())
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        fresh.append(row)

    for i in range(0, len(fresh), batch_size):
        batch = fresh[i : i + batch_size]
        vectors = embeddings.embed_texts([job_text(r) for r in batch])
        for row, vec in zip(batch, vectors):
            db.add(Job(**row, embedding=vec))
    db.commit()
    return len(fresh), skipped


def ingest_csv(db: Session, path: Path) -> tuple[int, int]:
    return ingest_rows(db, read_csv(path))