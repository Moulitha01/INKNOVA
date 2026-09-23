const express = require("express");
const Note = require("../models/Note");
const { buildDocx, buildXml, buildTxt } = require("../utils/export");

const router = express.Router();

// GET /api/notes?q=searchTerm  -> list all notes, or search by keyword
router.get("/", async (req, res) => {
  try {
    const { q } = req.query;
    let notes;
    if (q && q.trim()) {
      notes = await Note.find(
        { $text: { $search: q.trim() } },
        { score: { $meta: "textScore" } }
      ).sort({ score: { $meta: "textScore" } });
    } else {
      notes = await Note.find().sort({ createdAt: -1 });
    }
    res.json(notes);
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch notes", details: err.message });
  }
});

// GET /api/notes/:id
router.get("/:id", async (req, res) => {
  try {
    const note = await Note.findById(req.params.id);
    if (!note) return res.status(404).json({ error: "Note not found" });
    res.json(note);
  } catch (err) {
    res.status(400).json({ error: "Invalid note id" });
  }
});

// POST /api/notes  -> save a new note (after user reviews/edits recognized text)
router.post("/", async (req, res) => {
  try {
    const { title, content, tags } = req.body;
    if (!content || !content.trim()) {
      return res.status(400).json({ error: "Note content is required" });
    }
    const note = await Note.create({
      title: title && title.trim() ? title.trim() : "Untitled note",
      content,
      tags: Array.isArray(tags) ? tags : [],
    });
    res.status(201).json(note);
  } catch (err) {
    res.status(500).json({ error: "Failed to save note", details: err.message });
  }
});

// PUT /api/notes/:id  -> update an existing note
router.put("/:id", async (req, res) => {
  try {
    const { title, content, tags } = req.body;
    const note = await Note.findByIdAndUpdate(
      req.params.id,
      { ...(title !== undefined && { title }), ...(content !== undefined && { content }), ...(tags !== undefined && { tags }) },
      { new: true, runValidators: true }
    );
    if (!note) return res.status(404).json({ error: "Note not found" });
    res.json(note);
  } catch (err) {
    res.status(500).json({ error: "Failed to update note", details: err.message });
  }
});

// DELETE /api/notes/:id
router.delete("/:id", async (req, res) => {
  try {
    const note = await Note.findByIdAndDelete(req.params.id);
    if (!note) return res.status(404).json({ error: "Note not found" });
    res.json({ message: "Note deleted" });
  } catch (err) {
    res.status(500).json({ error: "Failed to delete note", details: err.message });
  }
});

// GET /api/notes/:id/export/:format  -> download as docx | xml | txt
router.get("/:id/export/:format", async (req, res) => {
  try {
    const note = await Note.findById(req.params.id);
    if (!note) return res.status(404).json({ error: "Note not found" });

    const format = req.params.format.toLowerCase();
    const safeName = note.title.replace(/[^a-z0-9]/gi, "_").slice(0, 50) || "note";

    if (format === "docx") {
      const buffer = await buildDocx(note);
      res.setHeader(
        "Content-Type",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      );
      res.setHeader("Content-Disposition", `attachment; filename="${safeName}.docx"`);
      return res.send(buffer);
    }

    if (format === "xml") {
      res.setHeader("Content-Type", "application/xml");
      res.setHeader("Content-Disposition", `attachment; filename="${safeName}.xml"`);
      return res.send(buildXml(note));
    }

    if (format === "txt") {
      res.setHeader("Content-Type", "text/plain");
      res.setHeader("Content-Disposition", `attachment; filename="${safeName}.txt"`);
      return res.send(buildTxt(note));
    }

    return res.status(400).json({ error: "Unsupported format. Use docx, xml, or txt." });
  } catch (err) {
    res.status(500).json({ error: "Export failed", details: err.message });
  }
});

module.exports = router;
