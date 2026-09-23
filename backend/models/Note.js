const mongoose = require("mongoose");

const NoteSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: true,
      trim: true,
      default: "Untitled note",
    },
    content: {
      type: String,
      required: true,
    },
    tags: {
      type: [String],
      default: [],
    },
    sourceImage: {
      type: String, // stored filename, optional
      default: null,
    },
  },
  { timestamps: true }
);

// Full-text index over title + content powers the search endpoint
NoteSchema.index({ title: "text", content: "text", tags: "text" });

module.exports = mongoose.model("Note", NoteSchema);

