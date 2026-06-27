from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.services import tts_service

router = APIRouter()

def get_current_user():
    return {"id": "dev-user"}

class TTSRequest(BaseModel):
    text: str
    speed: float = 1.0
    voice: str = "en-GB-SoniaNeural"
    phrase_pauses: bool = True

class WordTTSRequest(BaseModel):
    word: str
    voice: str = "en-GB-SoniaNeural"

@router.post("/tts/generate")
async def tts_generate(
    req: TTSRequest,
    current_user: dict = Depends(get_current_user)
):
    return await tts_service.generate_tts(
        text=req.text,
        speed=req.speed,
        voice=req.voice,
        phrase_pauses=req.phrase_pauses
    )

@router.post("/tts/word")
async def tts_word(
    req: WordTTSRequest,
    current_user: dict = Depends(get_current_user)
):
    return await tts_service.generate_word_tts(req.word, req.voice)