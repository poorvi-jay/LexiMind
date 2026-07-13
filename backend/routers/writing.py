"""
Writing Router — Owner: M2 (F25, F31, F32)
Exposes /writing/autosave (F31) and /writing/documents CRUD (F32).

STATUS:
- /writing/autosave (F31): IMPLEMENTED (Task 14)
- /writing/documents CRUD (F32): NOT YET IMPLEMENTED (Task 15)

Design note: autosave maintains ONE "current draft" row per user in
saved_documents (found-or-created), not a separate table - see
Task 14 write-up for why writing_sessions (mentioned in the Build
Guide's comment) has no content column and can't be used for this.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models_temp import get_db, SavedDocument, User
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/writing", tags=["Writing"])


class AutosaveRequest(BaseModel):
    content: str


class AutosaveResponse(BaseModel):
    saved: bool


class DraftResponse(BaseModel):
    content: str


def _get_or_create_draft(db: Session, user_id: str) -> SavedDocument:
    """
    Finds the user's current draft (the most recently updated
    saved_documents row with no explicit save yet), or creates one.
    Single-draft-per-user model for autosave, per Task 14's design.
    """
    draft = (
        db.query(SavedDocument)
        .filter(SavedDocument.user_id == user_id)
        .order_by(SavedDocument.updated_at.desc())
        .first()
    )
    if draft is None:
        draft = SavedDocument(user_id=user_id, content="")
        db.add(draft)
        db.commit()
        db.refresh(draft)
    return draft


@router.get("/autosave", response_model=DraftResponse)
async def get_draft(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Load the user's current draft on page mount."""
    draft = _get_or_create_draft(db, current_user.id)
    return {"content": draft.content}


@router.patch("/autosave", response_model=AutosaveResponse)
async def autosave(
    req: AutosaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """F31: Save the user's current draft content."""
    draft = _get_or_create_draft(db, current_user.id)
    draft.content = req.content
    db.commit()
    return {"saved": True}