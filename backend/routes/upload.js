const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");

const router = express.Router();

// Keep uploads in memory - we only forward them to the ML service,
// we don't need to persist the raw photo by default
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 15 * 1024 * 1024 }, // 15MB
});

// POST /api/upload
// Accepts a multipart form with field "image", forwards it to the
// Python ML microservice for handwriting recognition, and returns
// the recognized text back to the frontend (not yet saved to DB).
router.post("/", upload.single("image"), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: "No image uploaded (expected field 'image')" });
  }

  const mlServiceUrl = process.env.ML_SERVICE_URL || "http://localhost:5001";

  try {
    const form = new FormData();
    form.append("image", req.file.buffer, {
      filename: req.file.originalname || "note.png",
      contentType: req.file.mimetype,
    });

    const response = await axios.post(`${mlServiceUrl}/recognize`, form, {
      headers: form.getHeaders(),
      maxContentLength: Infinity,
      maxBodyLength: Infinity,
      timeout: 120000, // model inference can take a while on CPU
    });

    return res.json(response.data);
  } catch (err) {
    if (err.code === "ECONNREFUSED") {
      return res.status(503).json({
        error: "ML service is not running. Start ml-service (python app.py) and try again.",
      });
    }
    if (err.response) {
      return res.status(err.response.status).json(err.response.data);
    }
    console.error("Upload/recognition error:", err.message);
    return res.status(500).json({ error: "Recognition failed", details: err.message });
  }
});

module.exports = router;
