import re
import torch
from transformers import pipeline

predictor = pipeline("text-generation", model="distilgpt2")
tokenizer = predictor.tokenizer
model = predictor.model


def predict_words(prefix: str) -> list[str]:

    if not prefix or not prefix.strip():
        return []
    
    prefix = prefix.rstrip()

    input_ids = tokenizer(prefix, return_tensors="pt").input_ids
    input_len = input_ids.shape[1]

    with torch.no_grad():
        output_ids = model.generate(
            input_ids,
            max_new_tokens=6,
            num_return_sequences=6,
            do_sample=True,
            temperature=0.8,
            pad_token_id=50256,
        )

    words = []
    for seq in output_ids:
        new_tokens = seq[input_len:]  # only the tokens generated, not the prompt
        generated_text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        match = re.match(r"\s*([a-zA-Z]+)", generated_text)
        if match:
            word = match.group(1)
            if word.lower() not in [w.lower() for w in words]:
                words.append(word)
        if len(words) == 3:
            break

    return words


def predict_phrase(prefix: str) -> str:
    """
    Generate a short (up to 5 new tokens, capped at 40 chars)
    phrase continuation for the given prefix.

    Per PRD rule: NEVER raises/returns an error for an empty or
    unusable result - returns "" so the frontend can hide the
    4th suggestion pill (AC-22).

    Fixed alongside predict_words(): uses token-based slicing
    (not character-slicing, which had an encode/decode alignment
    bug) and strips trailing whitespace before generating (avoids
    the "dangling space" issue that caused fragment-like output).
    """
    if not prefix or not prefix.strip():
        return ""

    prefix = prefix.rstrip()

    input_ids = tokenizer(prefix, return_tensors="pt").input_ids
    input_len = input_ids.shape[1]

    with torch.no_grad():
        output_ids = model.generate(
            input_ids,
            max_new_tokens=5,
            num_return_sequences=1,
            do_sample=True,
            temperature=0.7,
            pad_token_id=50256,
        )

    new_tokens = output_ids[0][input_len:]
    generated = tokenizer.decode(new_tokens, skip_special_tokens=True)

    phrase = generated.strip().split(".")[0]
    phrase = re.sub(r"[^a-zA-Z\s']", "", phrase).strip()

    if not re.search(r"[a-zA-Z]", phrase):
        return ""

    return phrase[:40]