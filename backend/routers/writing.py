"""
Writing Router — Owner: M2 (F25, F31, F32)
Exposes /writing/autosave (F31) and /writing/documents CRUD (F32).

STATUS:
- /writing/autosave (F31): IMPLEMENTED (Task 14)
- /writing/documents CRUD (F32): IMPLEMENTED (Task 15)

Design note: autosave maintains ONE "current draft" row per user in
saved_documents, explicitly flagged via is_draft=True. This flag was
added after a real bug: without it, autosave's "find most recently
updated row" logic could accidentally hijack and overwrite a named
document the user had just opened, since there was no way to tell
"the draft" apart from "a document you deliberately saved." Named
saves (via Save As) are always created with is_draft=False, so
autosave can never touch them.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
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


class SaveDocRequest(BaseModel):
    title: str
    content: str
    template: str | None = None


class DocumentSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentFull(BaseModel):
    id: str
    title: str
    content: str
    template: str | None
    updated_at: datetime

    class Config:
        from_attributes = True


class SaveDocResponse(BaseModel):
    id: str


class DeleteResponse(BaseModel):
    deleted: bool


def _get_or_create_draft(db: Session, user_id: str) -> SavedDocument:
    """
    Finds the user's dedicated autosave draft row (is_draft=True),
    or creates one. This is intentionally separate from any named
    document the user has saved via "Save As" - see module docstring.
    """
    draft = (
        db.query(SavedDocument)
        .filter(SavedDocument.user_id == user_id, SavedDocument.is_draft == True)
        .first()
    )
    if draft is None:
        draft = SavedDocument(user_id=user_id, content="", is_draft=True)
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


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """F32: List all of the user's saved documents, most recent first."""
    docs = (
        db.query(SavedDocument)
        .filter(SavedDocument.user_id == current_user.id)
        .order_by(SavedDocument.updated_at.desc())
        .all()
    )
    return docs


@router.post("/documents", response_model=SaveDocResponse)
async def save_document(
    req: SaveDocRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    F32: Save the current content as a new named document.
    Explicitly is_draft=False - named saves are never touched by
    autosave's find-or-create logic.
    """
    doc = SavedDocument(
        user_id=current_user.id,
        title=req.title or "Untitled Document",
        content=req.content,
        template=req.template,
        is_draft=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id}


@router.get("/documents/{doc_id}", response_model=DocumentFull)
async def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """F32: Load a specific saved document by id."""
    doc = (
        db.query(SavedDocument)
        .filter(SavedDocument.id == doc_id, SavedDocument.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """F32: Delete a saved document."""
    doc = (
        db.query(SavedDocument)
        .filter(SavedDocument.id == doc_id, SavedDocument.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(doc)
    db.commit()
    return {"deleted": True}