"""
Handwriting recognition using TrOCR, an open-source transformer OCR model
from Microsoft/Hugging Face, fine-tuned on the IAM Handwriting Database.

Model size is configurable via the TROCR_MODEL env var:
  microsoft/trocr-small-handwritten  -> ~250MB, low RAM, default here
  microsoft/trocr-base-handwritten   -> ~1.3GB, slightly better accuracy

Start with "small" if RAM is tight. Switch to "base" only if accuracy
on your actual samples isn't good enough - see README.
"""

import os
import gc
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from spellchecker import SpellChecker

_MODEL_NAME = os.environ.get("TROCR_MODEL", "microsoft/trocr-small-handwritten")

# Cap CPU thread usage - unrestricted PyTorch will spin up a thread pool
# sized to all your cores, which increases peak memory use for no real
# speed benefit on a small demo workload.
torch.set_num_threads(max(2, os.cpu_count() // 2 if os.cpu_count() else 2))

_device = "cuda" if torch.cuda.is_available() else "cpu"
_processor = None
_model = None
_spell = SpellChecker()


def load_model():
    """Loads the model once at service startup. First call downloads
    weights from Hugging Face if not already cached locally."""
    global _processor, _model
    if _model is None:
        print(f"Loading {_MODEL_NAME} on {_device} ... (first run downloads the model)")
        _processor = TrOCRProcessor.from_pretrained(_MODEL_NAME)
        _model = VisionEncoderDecoderModel.from_pretrained(_MODEL_NAME).to(_device)
        _model.eval()
        print("Model loaded.")
    return _model, _processor


def _clean_text(raw_text: str) -> str:
    """Best-effort spell correction on the raw OCR output. Only touches
    words the checker doesn't recognize, and only when it's confident,
    so it won't mangle names or unusual words."""
    words = raw_text.split()
    corrected = []
    for w in words:
        stripped = w.strip(".,!?;:\"'()")
        if not stripped or not stripped.isalpha():
            corrected.append(w)
            continue
        if stripped.lower() in _spell:
            corrected.append(w)
        else:
            suggestion = _spell.correction(stripped.lower())
            if suggestion and suggestion != stripped.lower():
                # Preserve original capitalization pattern
                if stripped[0].isupper():
                    suggestion = suggestion.capitalize()
                corrected.append(w.replace(stripped, suggestion))
            else:
                corrected.append(w)
    return " ".join(corrected)


def _recognize_line(image) -> str:
    """Runs TrOCR on a single line image and returns the raw decoded text.
    num_beams=2 (instead of 4) roughly halves decoding memory/time with
    only a small accuracy tradeoff - worth it on a laptop demo."""
    model, processor = load_model()
    pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(_device)
    with torch.no_grad():
        generated_ids = model.generate(
            pixel_values,
            max_length=128,
            num_beams=2,
        )
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    del pixel_values, generated_ids
    return text


def recognize_text(line_images: list) -> dict:
    """
    line_images: list of PIL.Image, one per text line (see preprocess.segment_lines)
    Returns: { "raw_text": str, "cleaned_text": str }
    Lines are joined with newlines so paragraph structure is preserved.
    """
    raw_lines = [_recognize_line(img) for img in line_images]
    raw_text = "\n".join(raw_lines)
    cleaned_text = "\n".join(_clean_text(line) for line in raw_lines)

    gc.collect()  # release intermediate tensors between requests

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
    }
