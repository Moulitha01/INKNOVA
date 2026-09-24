import React, { useEffect, useState, useCallback, useRef } from "react";
import { fetchNotes, deleteNote, exportUrl } from "../api";

function highlight(text, q) {
  const term = q.trim();
  if (!term) return text;
  const esc = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return text.split(new RegExp(`(${esc})`, "gi")).map((part, i) =>
    part.toLowerCase() === term.toLowerCase() ? <mark key={i}>{part}</mark> : part
  );
}

export default function NotesList({ refreshKey }) {
  const [notes, setNotes] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState({});
  const reqId = useRef(0);

  const load = useCallback(async (q) => {
    const id = ++reqId.current;
    setLoading(true);
    setError("");
    try {
      const res = await fetchNotes(q);
      if (id === reqId.current) setNotes(res.data);
    } catch (err) {
      if (id === reqId.current) setError("Couldn't load your notes. Is the backend running?");
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  }, []);

  // live search: waits 300ms after typing stops; also reloads after a save
  useEffect(() => {
    const t = setTimeout(() => load(query), 300);
    return () => clearTimeout(t);
  }, [query, refreshKey, load]);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this note?")) return;
    try {
      await deleteNote(id);
      load(query);
    } catch {
      setError("Couldn't delete the note.");
    }
  };

  const LIMIT = 220;

  return (
    <section className="card">
      <div className="card-head">
        <h2>Your notes</h2>
        <span className="muted">
          {notes.length} {notes.length === 1 ? "note" : "notes"}
        </span>
      </div>

      <div className="search-row">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by title, text or tag..."
          aria-label="Search notes"
        />
        {query && (
          <button className="link" onClick={() => setQuery("")}>
            Clear
          </button>
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {loading && notes.length === 0 && <p className="muted">Loading...</p>}
      {!loading && !error && notes.length === 0 && (
        <p className="empty">
          {query ? `No notes match "${query}".` : "No notes yet. Convert your first page above."}
        </p>
      )}

      <ul className="notes-list">
        {notes.map((note) => {
          const long = note.content.length > LIMIT;
          const expanded = !!open[note._id];
          const body = long && !expanded ? note.content.slice(0, LIMIT) + "..." : note.content;
          return (
            <li key={note._id} className="note-item">
              <div className="note-header">
                <strong>{highlight(note.title, query)}</strong>
                <span className="date">{new Date(note.createdAt).toLocaleDateString()}</span>
              </div>

              <p className="note-preview">{highlight(body, query)}</p>
              {long && (
                <button
                  className="link small"
                  onClick={() => setOpen((o) => ({ ...o, [note._id]: !expanded }))}
                >
                  {expanded ? "Show less" : "Show more"}
                </button>
              )}

              {note.tags?.length > 0 && (
                <div className="tags">
                  {note.tags.map((t) => (
                    <span key={t} className="tag">{t}</span>
                  ))}
                </div>
              )}

              <div className="actions">
                <a className="btn" href={exportUrl(note._id, "docx")}>Word</a>
                <a className="btn" href={exportUrl(note._id, "xml")}>XML</a>
                <a className="btn" href={exportUrl(note._id, "txt")}>TXT</a>
                <button onClick={() => handleDelete(note._id)} className="danger">
                  Delete
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}