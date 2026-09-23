"""
Image preprocessing for handwritten note photos.

Pipeline: grayscale -> resize -> flatten background (shadows, show-through,
faint ruled lines) -> deskew -> pad. The image fed to TrOCR stays grayscale.
Binarization is used ONLY inside segment_lines to find line positions and to
locate ruled/margin lines, which are then painted white in the crops.
"""

import os
import cv2
import numpy as np
from PIL import Image

TARGET_WIDTH = 1600                                          # normalise photo scale
HEADER_SKIP = float(os.environ.get("HEADER_SKIP", "0.0"))    # e.g. 0.12 skips top 12% (header table)


def _to_gray(pil_image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2GRAY)


def _resize(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    scale = TARGET_WIDTH / w
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(gray, (TARGET_WIDTH, int(h * scale)), interpolation=interp)


def _flatten_background(gray: np.ndarray) -> np.ndarray:
    """Estimate the paper (dark strokes removed by closing), subtract it,
    and drop faint stuff (show-through ink, light ruled lines).
    Result: dark ink on clean white, still grayscale."""
    bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    bg = cv2.medianBlur(bg, 51)
    diff = cv2.absdiff(bg, gray).astype(np.float32)
    diff[diff < 18] = 0                                   # kill faint marks
    hi = np.percentile(diff[diff > 0], 99.5) if (diff > 0).any() else 1.0
    diff = np.clip(diff * (255.0 / max(hi, 1.0)), 0, 255)
    return (255 - diff).astype(np.uint8)


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Pick the rotation (-5..5 deg) whose row projection is sharpest."""
    small = cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    ink = (small < 160).astype(np.uint8)
    if ink.sum() < 200:
        return gray
    h, w = ink.shape
    best_angle, best_score = 0.0, -1.0
    for a in np.arange(-5, 5.1, 0.5):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
        r = cv2.warpAffine(ink, m, (w, h), flags=cv2.INTER_NEAREST)
        score = float(np.var(r.sum(axis=1)))
        if score > best_score:
            best_angle, best_score = a, score
    if abs(best_angle) < 0.5:
        return gray
    H, W = gray.shape
    m = cv2.getRotationMatrix2D((W / 2, H / 2), best_angle, 1.0)
    return cv2.warpAffine(gray, m, (W, H), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    gray = _resize(_to_gray(pil_image))
    flat = _flatten_background(gray)
    flat = _deskew(flat)
    padded = cv2.copyMakeBorder(flat, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    return Image.fromarray(cv2.cvtColor(padded, cv2.COLOR_GRAY2RGB))


def _ink_mask(gray: np.ndarray):
    """Returns (ink, lines_mask).
    ink: binary ink mask with long horizontal AND vertical strokes removed
         (ruled lines, underlines, table borders, margin lines).
    lines_mask: where those long strokes were, so they can be erased
         from the crops too."""
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    h = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1)))
    v = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80)))
    lines_mask = cv2.dilate(cv2.bitwise_or(h, v), np.ones((5, 5), np.uint8))
    ink = cv2.bitwise_and(ink, cv2.bitwise_not(lines_mask))
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))  # remove specks
    return ink, lines_mask


def segment_lines(pil_image: Image.Image, min_line_height: int = 18) -> list:
    """Split the page into single-line crops (top to bottom).
    Detection uses the ink mask; crops come from the grayscale image with
    ruled/margin lines painted white, trimmed horizontally to the ink so the
    text fills the frame."""
    gray = np.array(pil_image.convert("L"))
    H, W = gray.shape
    ink, lines_mask = _ink_mask(gray)

    clean = gray.copy()
    clean[lines_mask > 0] = 255
    clean_img = Image.fromarray(cv2.cvtColor(clean, cv2.COLOR_GRAY2RGB))

    top_skip = int(H * HEADER_SKIP)
    ink[:top_skip, :] = 0

    rows = (ink > 0).sum(axis=1).astype(np.float32)
    rows = np.convolve(rows, np.ones(5) / 5, mode="same")
    nz = rows[rows > 0]
    if nz.size == 0:
        return [pil_image]
    thresh = max(3.0, 0.05 * np.percentile(nz, 90))

    bands, in_band, start = [], False, 0
    for y, v in enumerate(rows):
        if v > thresh and not in_band:
            in_band, start = True, y
        elif v <= thresh and in_band:
            in_band = False
            bands.append([start, y])
    if in_band:
        bands.append([start, H])

    # merge bands separated by tiny gaps (dots on i, accents, etc.)
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] < 6:
            merged[-1][1] = b[1]
        else:
            merged.append(b)

    crops = []
    for s, e in merged:
        if e - s < min_line_height:
            continue
        cols = np.where((ink[s:e, :] > 0).sum(axis=0) > 0)[0]
        if cols.size < 25:                       # too little ink to be a line
            continue
        x0, x1 = max(0, cols[0] - 25), min(W, cols[-1] + 25)
        y0, y1 = max(0, s - 10), min(H, e + 10)
        crops.append(clean_img.crop((x0, y0, x1, y1)))

    return crops if crops else [pil_image]