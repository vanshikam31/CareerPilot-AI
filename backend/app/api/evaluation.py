import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.evaluation.agent_metrics import compute_agent_metrics
from app.evaluation.retrieval_eval import REPORT_PATH
from app.models.user import User
from app.schemas.evaluation import AgentMetricsOut

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.get("/agent", response_model=AgentMetricsOut)
def agent_metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Metrics from YOUR own conversations with the agent."""
    return compute_agent_metrics(db, user.id)


@router.get("/retrieval")
def retrieval_report(user: User = Depends(get_current_user)):
    """The last report written by `python run_evaluation.py`."""
    if not REPORT_PATH.exists():
        raise HTTPException(404, "No report yet. Run: python run_evaluation.py")
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))