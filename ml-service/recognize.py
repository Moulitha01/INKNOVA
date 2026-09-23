"""
Handwriting recognition with TrOCR (Hugging Face), one line at a time.

Env vars:
  TROCR_MODEL  default microsoft/trocr-base-handwritten
  NUM_BEAMS    default 5 (use 2 for faster CPU runs)
  SPELLCHECK   default 1 (set 0 to return raw text as cleaned_text)
"""

import os
import gc
import time
import difflib
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from spellchecker import SpellChecker

_MODEL_NAME = os.environ.get("TROCR_MODEL", "microsoft/trocr-base-handwritten")
_NUM_BEAMS = int(os.environ.get("NUM_BEAMS", "5"))
_SPELLCHECK = os.environ.get("SPELLCHECK", "1") == "1"

torch.set_num_threads(max(2, os.cpu_count() // 2 if os.cpu_count() else 2))

_device = "cuda" if torch.cuda.is_available() else "cpu"
_processor = None
_model = None
_spell = SpellChecker(distance=1)   # only fix single-edit misreads

# Subject vocabulary: near-miss words snap to these. Keep it specific to the
# notes you're digitising; add or remove words freely.
_DOMAIN = [
    "disaster", "disasters", "management", "natural", "earthquake", "cyclone",
    "flood", "landslide", "forest", "precautions", "prevented", "avoided",
    "occurred", "constructions", "buildings", "houses", "effects", "damage",
    "assessment", "internal", "types", "made", "areas", "street", "city",
]


def load_model():
    global _processor, _model
    if _model is None:
        print(f"Loading {_MODEL_NAME} on {_device} ...")
        _processor = TrOCRProcessor.from_pretrained(_MODEL_NAME)
        _model = VisionEncoderDecoderModel.from_pretrained(_MODEL_NAME).to(_device)
        _model.eval()
        print("Model loaded.")
    return _model, _processor


def _clean_text(raw_text: str) -> str:
    """Conservative cleanup:
    1) snap near-misses to the subject vocabulary (cutoff 0.8),
    2) otherwise fix unknown words of 4+ letters only when the spell-checker
       finds exactly one single-edit candidate.
    Everything else is left untouched."""
    if not _SPELLCHECK:
        return raw_text
    out = []
    for w in raw_text.split():
        core = w.strip(".,!?;:\"'()")
        if len(core) < 4 or not core.isalpha():
            out.append(w)
            continue
        low = core.lower()

        if low in _DOMAIN:
            out.append(w)
            continue
        m = difflib.get_close_matches(low, _DOMAIN, n=1, cutoff=0.8)
        if m:
            fix = m[0].capitalize() if core[0].isupper() else m[0]
            out.append(w.replace(core, fix))
            continue

        if low in _spell:
            out.append(w)
            continue
        cands = _spell.candidates(low)
        if cands and len(cands) == 1:            # unambiguous only
            fix = next(iter(cands))
            if core[0].isupper():
                fix = fix.capitalize()
            out.append(w.replace(core, fix))
        else:
            out.append(w)
    return " ".join(out)


def _is_degenerate(text: str) -> bool:
    tokens = text.split()
    if len(tokens) < 8:
        return False
    most_common = max(set(tokens), key=tokens.count)
    return tokens.count(most_common) / len(tokens) > 0.5


def _recognize_line(image) -> str:
    model, processor = load_model()
    pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(_device)
    with torch.no_grad():
        ids = model.generate(
            pixel_values,
            max_length=96,
            num_beams=_NUM_BEAMS,
            early_stopping=True,
            no_repeat_ngram_size=3,
        )
    text = processor.batch_decode(ids, skip_special_tokens=True)[0]
    del pixel_values, ids
    return text


def recognize_text(line_images: list) -> dict:
    """line_images: list of PIL images, one per line (see preprocess.segment_lines).
    Returns {"raw_text": str, "cleaned_text": str}."""
    print(f"Recognizing {len(line_images)} lines (beams={_NUM_BEAMS}) ...")
    raw_lines = []
    for i, img in enumerate(line_images, 1):
        t = time.time()
        raw_lines.append(_recognize_line(img))
        print(f"  line {i}/{len(line_images)} done in {time.time() - t:.1f}s")

    raw_lines = ["" if _is_degenerate(l) else l for l in raw_lines]
    raw_lines = [l for l in raw_lines if l.strip()]

    gc.collect()
    return {
        "raw_text": "\n".join(raw_lines),
        "cleaned_text": "\n".join(_clean_text(l) for l in raw_lines),
    }