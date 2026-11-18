"""Run from the backend folder:  python run_evaluation.py
Needs the database to be running and seeded (python seed_jobs.py)."""
import json
import sys

from app.database.session import SessionLocal
from app.evaluation.retrieval_eval import (
    DOCS_DIR,
    REPORT_PATH,
    load_dataset,
    run_evaluation,
    to_markdown,
)


def main() -> None:
    dataset = load_dataset()
    with SessionLocal() as db:
        try:
            report = run_evaluation(db, dataset)
        except ValueError as exc:
            sys.exit(str(exc))

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    DOCS_DIR.mkdir(exist_ok=True)
    markdown = to_markdown(report)
    (DOCS_DIR / "evaluation_report.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Saved: {REPORT_PATH} and docs\\evaluation_report.md")


if __name__ == "__main__":
    main()