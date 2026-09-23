"""
ML microservice for the Handwritten Notes Digitizer.

Exposes a single endpoint that the Node/Express backend calls:
  POST /recognize   (multipart form, field name "image")
  -> { "raw_text": "...", "cleaned_text": "...", "line_count": N }

Run standalone:
  python app.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import io

from preprocess import preprocess_image, segment_lines
from recognize import recognize_text, load_model

app = Flask(__name__)
CORS(app)

MAX_IMAGE_MB = 15


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
        result = recognize_text(lines)
        result["line_count"] = len(lines)
        return jsonify(result)
    except Exception as e:
        app.logger.exception("Recognition failed")
        return jsonify({"error": f"Recognition failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("Warming up model at startup so the first upload isn't slow...")
    load_model()
    app.run(host="0.0.0.0", port=5001, debug=False)
