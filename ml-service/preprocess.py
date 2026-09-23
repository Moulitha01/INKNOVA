"""
Image preprocessing for handwritten note photos.
Uses OpenCV to clean up a raw photo before it goes into the OCR model:
grayscale -> denoise -> deskew -> adaptive threshold -> pad.
"""

import cv2
import numpy as np
from PIL import Image


def _to_cv2(pil_image: Image.Image) -> np.ndarray:
    rgb = pil_image.convert("RGB")
    arr = np.array(rgb)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Estimate and correct small rotation angles using the minAreaRect
    of all non-background pixels."""
    inverted = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(inverted > 30))
    if coords.shape[0] < 20:
        return gray

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5 or abs(angle) > 15:
        # Ignore negligible or clearly-wrong estimates
        return gray

    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray, matrix, (w, h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    """
    Takes a raw PIL image (as uploaded by the user) and returns a cleaned
    PIL image ready for the OCR model.
    """
    cv_img = _to_cv2(pil_image)

    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    # Denoise while preserving edges (important for thin pen strokes)
    denoised = cv2.fastNlMeansDenoising(gray, h=15)

    # Correct skew from an off-angle photo
    deskewed = _deskew(denoised)

    # Adaptive threshold handles uneven lighting/shadows better than a
    # single global threshold
    thresh = cv2.adaptiveThreshold(
        deskewed, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=15,
    )

    # Light dilation to reconnect thin, broken pen strokes
    kernel = np.ones((1, 1), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # Pad with white border - helps the transformer model, which was
    # trained on images with margin around the text
    padded = cv2.copyMakeBorder(
        cleaned, 20, 20, 20, 20,
        cv2.BORDER_CONSTANT, value=255
    )

    rgb = cv2.cvtColor(padded, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(rgb)


def segment_lines(pil_image: Image.Image, min_line_height: int = 12) -> list:
    """
    Splits a full preprocessed page into individual text-line images using
    a horizontal projection profile (row-wise dark-pixel density).

    TrOCR is trained on single text lines, not full pages, so this step is
    what lets the pipeline handle a real handwritten page instead of just
    one line of writing.

    Returns a list of PIL images, one per detected line, top to bottom.
    """
    gray = np.array(pil_image.convert("L"))
    inverted = cv2.bitwise_not(gray)  # ink becomes bright, background dark

    row_sums = np.sum(inverted > 40, axis=1)
    threshold = max(2, int(row_sums.max() * 0.02)) if row_sums.max() > 0 else 2

    lines = []
    in_line = False
    start = 0
    for y, val in enumerate(row_sums):
        if val > threshold and not in_line:
            in_line = True
            start = y
        elif val <= threshold and in_line:
            in_line = False
            end = y
            if end - start >= min_line_height:
                lines.append((start, end))
    if in_line and (len(row_sums) - start) >= min_line_height:
        lines.append((start, len(row_sums)))

    if not lines:
        # Fall back to treating the whole image as one line
        return [pil_image]

    line_images = []
    pad = 6
    h = gray.shape[0]
    for start, end in lines:
        top = max(0, start - pad)
        bottom = min(h, end + pad)
        cropped = pil_image.crop((0, top, pil_image.width, bottom))
        line_images.append(cropped)

    return line_images
