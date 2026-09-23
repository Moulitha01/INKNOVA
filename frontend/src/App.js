import React, { useState } from "react";
import UploadNote from "./components/UploadNote";
import NotesList from "./components/NotesList";
import "./index.css";

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="app">
      <header>
        <h1>Handwritten Notes Digitizer</h1>
        <p className="subtitle">
          Convert handwritten notes into editable, searchable digital text -
          built entirely with open source software.
        </p>
      </header>

      <main>
        <UploadNote onSaved={() => setRefreshKey((k) => k + 1)} />
        <NotesList refreshKey={refreshKey} />
      </main>

      <footer>
        <p>MERN stack + OpenCV + TrOCR (open source handwriting recognition)</p>
      </footer>
    </div>
  );
}
