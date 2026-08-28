from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: runs once before the app starts accepting requests
    init_db()
    yield
    # Shutdown: nothing needed yet, but this is where cleanup would go


app = FastAPI(title="LexiMind AI API", version="5.0", lifespan=lifespan)

configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
allowed_origins = list(dict.fromkeys([
    *configured_origins,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routers.ocr import router as ocr_router
from backend.routers.tts import router as tts_router
from backend.routers.reading import router as reading_router
from backend.routers.classify import router as classify_router 
from backend.routers.sessions import router as sessions_router
from backend.routers.analytics import router as analytics_router
from backend.routers.nlp import router as nlp_router
from backend.routers.auth import router as auth_router
from backend.routers.writing import router as writing_router
from backend.models_temp import init_db

app.include_router(nlp_router)
app.include_router(auth_router)
app.include_router(writing_router)
app.include_router(ocr_router, tags=["OCR"])
app.include_router(tts_router, tags=["TTS"])
app.include_router(reading_router, tags=["Reading"])
app.include_router(classify_router, tags=["Classify"])  
app.include_router(sessions_router, tags=["Sessions"])
app.include_router(analytics_router, tags=["Analytics"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "5.0"}
