"""Run from the backend folder:  python seed_jobs.py"""
import sys
from pathlib import Path

from app.database.session import SessionLocal, init_db
from app.services.job_ingest import ingest_csv


def main() -> None:
    default = Path(__file__).resolve().parent.parent / "data" / "sample_jobs.csv"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not path.exists():
        sys.exit(f"CSV not found: {path}\nRun first:  python ..\\data\\generate_jobs.py")

    init_db()
    print("Embedding jobs (first run downloads the model, ~130 MB)...")
    with SessionLocal() as db:
        added, skipped = ingest_csv(db, path)
    print(f"Done. Added {added} jobs, skipped {skipped} duplicates.")


if __name__ == "__main__":
    main()