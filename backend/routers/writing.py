"""
Writing Router — Owner: M2 (F25, F31, F32)
Exposes /writing/documents CRUD endpoints.

STATUS: Skeleton only. Depends on Auth existing first
(documents are user-scoped), so this is built last.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/writing", tags=["Writing"])

# Endpoints added later (Writing Notepad phase).