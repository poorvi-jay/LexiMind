import easyocr
import cv2
import numpy as np
import pdfplumber
import asyncio
from io import BytesIO
from fastapi import HTTPException

# Load EasyOCR once at module level — never reload per request
reader = easyocr.Reader(['en'], gpu=False)

def preprocess_image(img_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cleaned = cv2.fastNlMeansDenoising(thresh, h=10)
    return cleaned

def _extract_from_image_sync(img_bytes: bytes) -> str:
    cleaned = preprocess_image(img_bytes)
    results = reader.readtext(cleaned)
    text = " ".join([res[1] for res in results])
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text. Please try a clearer image or paste text manually.")
    return text

async def extract_from_image(img_bytes: bytes) -> str:
    # Run in thread pool — EasyOCR is CPU-blocking
    return await asyncio.to_thread(_extract_from_image_sync, img_bytes)

def _extract_from_pdf_sync(pdf_bytes: bytes):
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages = len(pdf.pages)
            text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
            if text.strip():
                return text, pages

            # Scanned PDF fallback — use pdf2image + EasyOCR
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(pdf_bytes)
            pages = len(images)
            all_text = []
            for img in images:
                img_array = np.array(img)
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                results = reader.readtext(img_bgr)
                all_text.append(" ".join([r[1] for r in results]))
            return "\n".join(all_text), pages

    except Exception as e:
        if "password" in str(e).lower():
            raise HTTPException(status_code=400, detail="This PDF is password-protected. Please unlock it and try again.")
        raise HTTPException(status_code=400, detail="Could not process PDF.")

async def extract_from_pdf(pdf_bytes: bytes):
    return await asyncio.to_thread(_extract_from_pdf_sync, pdf_bytes)