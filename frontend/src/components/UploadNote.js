import React, { useState, useRef, useEffect } from "react";
import { recognizeImage, saveNote } from "../api";

const STATUS = [
  "Cleaning up the photo...",
  "Finding the lines of handwriting...",
  "Reading line by line...",
  "Still reading, long notes take a little while...",
];

function friendlyError(err) {
  if (err.code === "ECONNABORTED") {
    return "This is taking longer than expected. Try a smaller or clearer photo.";
  }
  if (err.response?.data?.error) return err.response.data.error;
  if (err.request && !err.response) {
    return "Can't reach the server. Check that the backend and ML service are running.";
  }
  return "Recognition failed. Please try again.";
}

export default function UploadNote({ onSaved }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [raw, setRaw] = useState("");
  const [cleaned, setCleaned] = useState("");
  const [mode, setMode] = useState("cleaned");
  const [hasResult, setHasResult] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const inputRef = useRef(null);

  // free the preview URL when it changes
  useEffect(() => {
    return () => preview && URL.revokeObjectURL(preview);
  }, [preview]);

  // elapsed-seconds timer while recognizing
  useEffect(() => {
    if (!loading) return;
    setElapsed(0);
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [loading]);

  const pickFile = (f) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) {
      setError("Please choose an image file (JPG, PNG, ...).");
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setText("");
    setRaw("");
    setCleaned("");
    setHasResult(false);
    setError("");
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setTitle("");
    setText("");
    setTags("");
    setRaw("");
    setCleaned("");
    setHasResult(false);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  };

  const handleConvert = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const res = await recognizeImage(file);
      const c = res.data.cleaned_text || "";
      const r = res.data.raw_text || "";
      setCleaned(c);
      setRaw(r);
      setMode(c ? "cleaned" : "raw");
      setText(c || r);
      if (!(c || r).trim()) {
        setError("No text was detected. Try a clearer, well-lit photo.");
      } else {
        setHasResult(true);
        if (!title) setTitle(`Note - ${new Date().toLocaleDateString()}`);
      }
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (next) => {
    if (next === mode) return;
    const current = mode === "cleaned" ? cleaned : raw;
    if (text !== current && !window.confirm("Switching will replace your edits. Continue?")) {
      return;
    }
    setMode(next);
    setText(next === "cleaned" ? cleaned : raw);
  };

  const handleSave = async () => {
    if (!text.trim()) {
      setError("Nothing to save yet.");
      return;
    }
    setSaving(true);
    try {
      const tagList = tags.split(",").map((t) => t.trim()).filter(Boolean);
      await saveNote({ title, content: text, tags: tagList });
      reset();
      setNotice("Note saved.");
      setTimeout(() => setNotice(""), 3000);
      onSaved && onSaved();
    } catch (err) {
      setError(err.response?.data?.error || "Failed to save note.");
    } finally {
      setSaving(false);
    }
  };

  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const statusMsg = STATUS[Math.min(Math.floor(elapsed / 15), STATUS.length - 1)];

  return (
    <section className="card">
      <div className="card-head">
        <h2>Convert a handwritten note</h2>
        {preview && (
          <button className="link" onClick={reset} disabled={loading}>
            Start over
          </button>
        )}
      </div>

      {notice && <p className="notice">{notice}</p>}

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => pickFile(e.target.files?.[0])}
      />

      {!preview ? (
        <div
          className={`dropzone ${dragging ? "dragging" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
        >
          <div className="dz-icon">📄</div>
          <p className="dz-title">Drop a photo of your note here</p>
          <p className="dz-sub">or click to browse. Phone photos work fine.</p>
        </div>
      ) : (
        <div className="workspace">
          <div className="pane-image">
            <img src={preview} alt="Your handwritten note" />
            <p className="file-name">{file?.name}</p>
          </div>

          <div className="pane-form">
            {!hasResult && !loading && (
              <button className="primary big" onClick={handleConvert}>
                Convert to text
              </button>
            )}

            {loading && (
              <div className="progress" aria-live="polite">
                <div className="bar"><span /></div>
                <p className="status">{statusMsg}</p>
                <p className="hint">
                  {elapsed}s elapsed. The AI model reads one line at a time, so
                  a full page can take a minute or two.
                </p>
              </div>
            )}

            {error && <p className="error">{error}</p>}

            {hasResult && (
              <>
                <label htmlFor="note-title">Title</label>
                <input
                  id="note-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />

                <div className="label-row">
                  <label htmlFor="note-text">Recognized text (edit as needed)</label>
                  {raw && cleaned && raw !== cleaned && (
                    <div className="seg" role="group" aria-label="Text version">
                      <button
                        type="button"
                        className={mode === "cleaned" ? "on" : ""}
                        onClick={() => switchMode("cleaned")}
                      >
                        Cleaned
                      </button>
                      <button
                        type="button"
                        className={mode === "raw" ? "on" : ""}
                        onClick={() => switchMode("raw")}
                      >
                        Original
                      </button>
                    </div>
                  )}
                </div>
                <textarea
                  id="note-text"
                  rows={16}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
                <p className="count">{words} words. Compare with the photo and fix any mistakes.</p>

                <label htmlFor="note-tags">Tags (comma separated)</label>
                <input
                  id="note-tags"
                  type="text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="e.g. lecture, chemistry, chapter3"
                />

                <button className="primary big" onClick={handleSave} disabled={saving}>
                  {saving ? "Saving..." : "Save note"}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {!preview && error && <p className="error">{error}</p>}
    </section>
  );
}