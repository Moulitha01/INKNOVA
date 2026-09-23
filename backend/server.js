require("dotenv").config();
const express = require("express");
const cors = require("cors");
const connectDB = require("./config/db");
const uploadRoute = require("./routes/upload");
const notesRoute = require("./routes/notes");

const app = express();

app.use(cors());
app.use(express.json({ limit: "5mb" }));

connectDB();

app.get("/api/health", (req, res) => res.json({ status: "ok" }));
app.use("/api/upload", uploadRoute);
app.use("/api/notes", notesRoute);

app.use((req, res) => res.status(404).json({ error: "Not found" }));

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`Backend running on http://localhost:${PORT}`));
