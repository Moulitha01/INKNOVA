import React, { useState } from "react";
import { recognizeImage, saveNote } from "../api";

export default function UploadNote({ onSaved }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setText("");
    setError("");
  };

  const handleConvert = async () => {
    if (!file) {
      setError("Choose an image of a handwritten note first.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await recognizeImage(file);
      setText(res.data.cleaned_text || res.data.raw_text || "");
      if (!title) {
        setTitle(`Note - ${new Date().toLocaleDateString()}`);
      }
    } catch (err) {
      setError(
        err.response?.data?.error || "Recognition failed. Is the ML service running?"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!text.trim()) {
      setError("Nothing to save yet - convert an image first.");
      return;
    }
    try {
      const tagList = tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await saveNote({ title, content: text, tags: tagList });
      setFile(null);
      setPreview(null);
      setTitle("");
      setText("");
      setTags("");
      setError("");
      onSaved && onSaved();
    } catch (err) {
      setError(err.response?.data?.error || "Failed to save note.");
    }
  };

  return (
    <div className="card">
      <h2>Convert a handwritten note</h2>

      <input type="file" accept="image/*" onChange={handleFileChange} />

      {preview && (
        <img src={preview} alt="preview" className="preview" />
      )}

      <button onClick={handleConvert} disabled={!file || loading}>
        {loading ? "Recognizing..." : "Convert to text"}
      </button>

      {error && <p className="error">{error}</p>}

      {text && (
        <>
          <label>Title</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} />

          <label>Recognized text (edit as needed)</label>
          <textarea
            rows={10}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />

          <label>Tags (comma separated)</label>
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="e.g. lecture, chemistry, chapter3"
          />

          <button onClick={handleSave} className="primary">
            Save note
          </button>
        </>
      )}
    </div>
  );
}
