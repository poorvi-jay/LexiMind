import edge_tts
import base64
import hashlib
import re

from fastapi import HTTPException

# ── Cache ──
_tts_cache = {}
MAX_CACHE = 20
MAX_TTS_CHARS = 1000  # ~150 words, ~30s of audio

# ── Phrase pause injection ──
PAUSE_MARKER = "... "
BOUNDARY_PATTERNS = [
    r'(,\s)',
    r'(;\s)',
    r'(:\s)',
    r'(\s—\s)',
    r'(\bbecause\b)',
    r'(\balthough\b)',
    r'(\bhowever\b)',
    r'(\btherefore\b)',
]


def inject_phrase_pauses(text: str) -> str:
    for pattern in BOUNDARY_PATTERNS:
        text = re.sub(pattern, PAUSE_MARKER + r'\1', text)
    return text


def speed_to_rate(speed: float) -> str:
    percent = int((speed - 1.0) * 100)
    return f"+{percent}%" if percent >= 0 else f"{percent}%"


# ─────────────────────────────────────────────
#  Word splitting — MUST match frontend logic
# ─────────────────────────────────────────────
def split_words_for_timing(text: str) -> list[str]:
    """
    Split using whitespace — identical to frontend's
        text.split(/\\s+/).filter(w => w.length > 0)
    This ensures word_timings indices match the WordDisplay array.
    """
    return [w for w in text.split() if w]


# ─────────────────────────────────────────────
#  MP3 duration — frame-accurate parser
# ─────────────────────────────────────────────
def get_mp3_duration_ms(audio_bytes: bytes) -> int:
    """
    Parse MP3 frame headers to calculate actual duration.
    Falls back to 48kbps byte-size estimation.
    """
    try:
        duration_ms = 0.0
        i = 0
        data = audio_bytes
        length = len(data)

        bitrate_table = [
            0, 32, 40, 48, 56, 64, 80, 96,
            112, 128, 160, 192, 224, 256, 320, 0,
        ]
        sample_rate_table = [44100, 48000, 32000, 0]

        frame_count = 0
        while i < length - 4:
            if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
                version = (data[i + 1] >> 3) & 0x03
                layer = (data[i + 1] >> 1) & 0x03
                bitrate_idx = (data[i + 2] >> 4) & 0x0F
                sr_idx = (data[i + 2] >> 2) & 0x03

                if (
                    version == 3
                    and layer == 1
                    and 0 < bitrate_idx < 15
                    and sr_idx < 3
                ):
                    bitrate = bitrate_table[bitrate_idx] * 1000
                    sample_rate = sample_rate_table[sr_idx]
                    padding = (data[i + 2] >> 1) & 0x01
                    frame_size = (144 * bitrate // sample_rate) + padding

                    if frame_size > 0:
                        duration_ms += 1152 * 1000 / sample_rate
                        i += frame_size
                        frame_count += 1
                        continue
            i += 1

        if frame_count > 10:
            return int(duration_ms)
    except Exception:
        pass

    # Fallback — edge-tts outputs ~48 kbps → 6 bytes/ms
    return int(len(audio_bytes) / 6)


# ─────────────────────────────────────────────
#  Timing: estimated (fallback)
# ─────────────────────────────────────────────
def estimate_word_timings(words: list[str], total_duration_ms: int) -> list[dict]:
    if not words or total_duration_ms <= 0:
        return []

    gap_budget_ms = int(total_duration_ms * 0.05)
    speech_budget_ms = total_duration_ms - gap_budget_ms
    gap_per_word_ms = gap_budget_ms // max(len(words), 1)

    char_counts = [max(len(w), 1) for w in words]
    total_chars = sum(char_counts)

    timings = []
    current_ms = 0

    for i, word in enumerate(words):
        word_duration = int((char_counts[i] / total_chars) * speech_budget_ms)
        timings.append({
            "word": word,
            "start_ms": current_ms,
            "end_ms": current_ms + word_duration,
        })
        current_ms += word_duration + gap_per_word_ms

    return timings


# ─────────────────────────────────────────────
#  Timing: real WordBoundary → display words
# ─────────────────────────────────────────────
def map_boundaries_to_display_words(
    raw_boundaries: list[dict],
    display_words: list[str],
    total_duration_ms: int,
) -> list[dict]:
    """
    Greedy character matching — consume boundary entries
    until they cover each display word.
    """
    if not raw_boundaries:
        return estimate_word_timings(display_words, total_duration_ms)

    timings = []
    b_idx = 0

    for display_word in display_words:
        display_clean = re.sub(r'[^a-zA-Z0-9]', '', display_word).lower()

        if b_idx >= len(raw_boundaries):
            last_end = timings[-1]["end_ms"] if timings else 0
            timings.append({
                "word": display_word,
                "start_ms": int(last_end),
                "end_ms": int(last_end + 200),
            })
            continue

        start_ms = raw_boundaries[b_idx]["offset_ms"]
        end_ms = start_ms + raw_boundaries[b_idx]["duration_ms"]
        consumed = re.sub(
            r'[^a-zA-Z0-9]', '', raw_boundaries[b_idx]["text"]
        ).lower()
        b_idx += 1

        while consumed != display_clean and b_idx < len(raw_boundaries):
            boundary = raw_boundaries[b_idx]
            end_ms = boundary["offset_ms"] + boundary["duration_ms"]
            consumed += re.sub(
                r'[^a-zA-Z0-9]', '', boundary["text"]
            ).lower()
            b_idx += 1
            if display_clean in consumed:
                break

        timings.append({
            "word": display_word,
            "start_ms": int(start_ms),
            "end_ms": int(end_ms),
        })

    return timings


# ─────────────────────────────────────────────
#  Core TTS generation (shared logic)
# ─────────────────────────────────────────────
async def _run_edge_tts(text: str, tts_text: str, speed: float, voice: str):
    """
    Calls edge-tts, collects audio + WordBoundary events,
    builds word_timings aligned to the *display* word list.
    Returns (audio_bytes, word_timings, duration_ms).
    """
    display_words = split_words_for_timing(text.strip())

    rate = speed_to_rate(speed)
    communicate = edge_tts.Communicate(tts_text, voice, rate=rate)

    audio_chunks = []
    raw_boundaries = []

    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                raw_boundaries.append({
                    "text": chunk["text"],
                    "offset_ms": chunk["offset"] / 10_000,
                    "duration_ms": chunk["duration"] / 10_000,
                })
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="TTS unavailable. Check your internet connection.",
        )

    if not audio_chunks:
        raise HTTPException(
            status_code=503,
            detail="TTS unavailable. Check your internet connection.",
        )

    audio_bytes = b"".join(audio_chunks)
    total_duration_ms = get_mp3_duration_ms(audio_bytes)

    if raw_boundaries:
        word_timings = map_boundaries_to_display_words(
            raw_boundaries, display_words, total_duration_ms
        )
    else:
        word_timings = estimate_word_timings(display_words, total_duration_ms)

    return audio_bytes, word_timings, total_duration_ms


def _truncate_text(text: str) -> str:
    if len(text) <= MAX_TTS_CHARS:
        return text
    return text[:MAX_TTS_CHARS].rsplit(' ', 1)[0]


# ─────────────────────────────────────────────
#  Public: JSON endpoint (base64)
# ─────────────────────────────────────────────
async def generate_tts(
    text: str,
    speed: float = 1.0,
    voice: str = "en-GB-SoniaNeural",
    phrase_pauses: bool = True,
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text provided for TTS.")

    text = _truncate_text(text.strip())

    cache_key = hashlib.md5(
        f"{text}{speed}{voice}{phrase_pauses}".encode()
    ).hexdigest()
    if cache_key in _tts_cache:
        cached = _tts_cache[cache_key]
        # Cache may hold raw bytes (from generate_tts_raw) — convert
        if "audio_b64" not in cached:
            cached = {
                **cached,
                "audio_b64": base64.b64encode(cached["audio_bytes"]).decode(),
            }
        return {
            "audio_b64": cached["audio_b64"],
            "word_timings": cached["word_timings"],
            "duration_ms": cached["duration_ms"],
        }

    tts_text = inject_phrase_pauses(text) if phrase_pauses else text
    audio_bytes, word_timings, duration_ms = await _run_edge_tts(
        text, tts_text, speed, voice
    )

    audio_b64 = base64.b64encode(audio_bytes).decode()

    result = {
        "audio_bytes": audio_bytes,
        "audio_b64": audio_b64,
        "word_timings": word_timings,
        "duration_ms": duration_ms,
    }

    _tts_cache[cache_key] = result
    if len(_tts_cache) > MAX_CACHE:
        del _tts_cache[next(iter(_tts_cache))]

    return {
        "audio_b64": audio_b64,
        "word_timings": word_timings,
        "duration_ms": duration_ms,
    }


# ─────────────────────────────────────────────
#  Public: Fast endpoint (raw bytes)
# ─────────────────────────────────────────────
async def generate_tts_raw(
    text: str,
    speed: float = 1.0,
    voice: str = "en-GB-SoniaNeural",
    phrase_pauses: bool = True,
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text provided for TTS.")

    text = _truncate_text(text.strip())

    cache_key = hashlib.md5(
        f"{text}{speed}{voice}{phrase_pauses}".encode()
    ).hexdigest()
    if cache_key in _tts_cache:
        cached = _tts_cache[cache_key]
        return {
            "audio_bytes": cached["audio_bytes"],
            "word_timings": cached["word_timings"],
            "duration_ms": cached["duration_ms"],
        }

    tts_text = inject_phrase_pauses(text) if phrase_pauses else text
    audio_bytes, word_timings, duration_ms = await _run_edge_tts(
        text, tts_text, speed, voice
    )

    result = {
        "audio_bytes": audio_bytes,
        "word_timings": word_timings,
        "duration_ms": duration_ms,
    }

    _tts_cache[cache_key] = result
    if len(_tts_cache) > MAX_CACHE:
        del _tts_cache[next(iter(_tts_cache))]

    return result


# ─────────────────────────────────────────────
#  Public: Single word TTS
# ─────────────────────────────────────────────
async def generate_word_tts(word: str, voice: str = "en-GB-SoniaNeural"):
    communicate = edge_tts.Communicate(word, voice)
    audio_chunks = []

    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
    except Exception:
        raise HTTPException(status_code=503, detail="TTS unavailable.")

    if not audio_chunks:
        raise HTTPException(status_code=503, detail="TTS unavailable.")

    audio_bytes = b"".join(audio_chunks)
    return {"audio_b64": base64.b64encode(audio_bytes).decode()}