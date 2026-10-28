"""
Template router for a canvas app backend.

Copy this file when building a new app (e.g. rag_app.py, summarizer_app.py):
  1. Rename the router and its request/response models.
  2. Replace the logic in `run()` with the real processing
     (RAG pipeline, model call, DB lookup, etc.).
  3. Register the new router in server/main.py with its own prefix.
  4. Add a matching entry to the `apps` registry in synaptiq.html,
     pointing `endpoint` at this router's path.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class PromptRequest(BaseModel):
    prompt: str


class PromptResponse(BaseModel):
    result: str


@router.post("/run", response_model=PromptResponse)
def run(request: PromptRequest) -> PromptResponse:
    """
    Template endpoint. Currently just echoes the prompt back so the
    canvas <-> server round trip can be tested end-to-end before any
    real processing logic is wired in.
    """
    return PromptResponse(result=f"Echo: {request.prompt}")
