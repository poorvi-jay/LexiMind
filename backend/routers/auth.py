"""
Auth Router — Owner: M2 (F01-F04)
Exposes /auth/register, /auth/login, /auth/me, /auth/preferences.

STATUS: Skeleton only. Built starting in the Auth phase, AFTER
NLP (F26-F28) and Prediction (F29) are complete and tested, per
Build Guide Section 0.1's revised build order.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])

# Endpoints added later (Auth phase).