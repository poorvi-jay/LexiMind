from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Annotated
from backend.services import ocr_service

router = APIRouter()

@router.post("/ocr/image")
async def ocr_image(file: Annotated[UploadFile, File()]):
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(422, "Please upload a JPG or PNG file.")
    img_bytes = await file.read()
    if len(img_bytes) > 10_000_000:
        raise HTTPException(413, "File too large. Maximum 10 MB allowed.")
    text = await ocr_service.extract_from_image(img_bytes)
    return {"text": text, "word_count": len(text.split())}

@router.post("/ocr/pdf")
async def ocr_pdf(file: Annotated[UploadFile, File()]):
    if file.content_type != "application/pdf":
        raise HTTPException(422, "Please upload a PDF file.")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10_000_000:
        raise HTTPException(413, "File too large. Maximum 10 MB allowed.")
    text, pages = await ocr_service.extract_from_pdf(pdf_bytes)
    return {"text": text, "word_count": len(text.split()), "pages": pages}