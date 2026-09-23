"""
ML microservice for the Handwritten Notes Digitizer.

Exposes a single endpoint that the Node/Express backend calls:
  POST /recognize   (multipart form, field name "image")
  -> { "raw_text": "...", "cleaned_text": "...", "line_count": N }

Run standalone:
  python app.py

Debugging: set DEBUG_SAVE_LINES=1 before running to save every detected
line crop as a PNG in ml-service/debug_lines/ so you can visually check
exactly what image the model is reading. This is the fastest way to tell
a preprocessing bug apart from a genuine recognition-accuracy limit.
  Windows:  $env:DEBUG_SAVE_LINES="1"; python app.py
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import io

from preprocess import preprocess_image, segment_lines
from recognize import recognize_text, load_model

app = Flask(__name__)
CORS(app)

MAX_IMAGE_MB = 15
DEBUG_SAVE_LINES = os.environ.get("DEBUG_SAVE_LINES") == "1"
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug_lines")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/recognize", methods=["POST"])
def recognize():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided (expected field 'image')"}), 400

    file = request.files["image"]
    raw_bytes = file.read()

    if len(raw_bytes) > MAX_IMAGE_MB * 1024 * 1024:
        return jsonify({"error": f"Image too large (max {MAX_IMAGE_MB}MB)"}), 400

    try:
        image = Image.open(io.BytesIO(raw_bytes))
    except Exception:
        return jsonify({"error": "Could not read image file"}), 400

    try:
        preprocessed = preprocess_image(image)
        lines = segment_lines(preprocessed)

        if DEBUG_SAVE_LINES:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            for f in os.listdir(DEBUG_DIR):
                os.remove(os.path.join(DEBUG_DIR, f))
            preprocessed.save(os.path.join(DEBUG_DIR, "_full_preprocessed.png"))
            for i, line_img in enumerate(lines):
                line_img.save(os.path.join(DEBUG_DIR, f"line_{i:02d}.png"))
            print(f"Saved {len(lines)} line crops to {DEBUG_DIR}")

        result = recognize_text(lines)
        result["line_count"] = len(lines)
        return jsonify(result)
    except Exception as e:
        app.logger.exception("Recognition failed")
        return jsonify({"error": f"Recognition failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("Warming up model at startup so the first upload isn't slow...")
    load_model()
    if DEBUG_SAVE_LINES:
        print(f"Debug mode: line crops will be saved to {DEBUG_DIR}")
    app.run(host="0.0.0.0", port=5001, debug=False)