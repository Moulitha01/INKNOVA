import React, { useEffect, useState, useCallback } from "react";
import { fetchNotes, deleteNote, exportUrl } from "../api";

export default function NotesList({ refreshKey }) {
  const [notes, setNotes] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (q) => {
    setLoading(true);
    try {
      const res = await fetchNotes(q);
      setNotes(res.data);
    } catch (err) {
      console.error("Failed to load notes", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  const handleSearch = (e) => {
    e.preventDefault();
    load(query);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this note?")) return;
    await deleteNote(id);
    load(query);
  };

  return (
    <div className="card">
      <h2>Your notes</h2>

      <form onSubmit={handleSearch} className="search-row">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search notes by keyword..."
        />
        <button type="submit">Search</button>
      </form>

      {loading && <p>Loading...</p>}
      {!loading && notes.length === 0 && <p>No notes yet.</p>}

      <ul className="notes-list">
        {notes.map((note) => (
          <li key={note._id} className="note-item">
            <div className="note-header">
              <strong>{note.title}</strong>
              <span className="date">
                {new Date(note.createdAt).toLocaleDateString()}
              </span>
            </div>
            <p className="note-preview">
              {note.content.slice(0, 160)}
              {note.content.length > 160 ? "..." : ""}
            </p>
            {note.tags?.length > 0 && (
              <div className="tags">
                {note.tags.map((t) => (
                  <span key={t} className="tag">
                    {t}
                  </span>
                ))}
              </div>
            )}
            <div className="actions">
              <a href={exportUrl(note._id, "docx")}>Export DOCX</a>
              <a href={exportUrl(note._id, "xml")}>Export XML</a>
              <a href={exportUrl(note._id, "txt")}>Export TXT</a>
              <button onClick={() => handleDelete(note._id)} className="danger">
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
