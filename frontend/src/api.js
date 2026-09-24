import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:5000/api";

export const recognizeImage = (file) => {
  const form = new FormData();
  form.append("image", file);
  return axios.post(`${API_BASE}/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300000, // CPU recognition can take a few minutes
  });
};

export const saveNote = (note) => axios.post(`${API_BASE}/notes`, note);

export const updateNote = (id, note) => axios.put(`${API_BASE}/notes/${id}`, note);

export const deleteNote = (id) => axios.delete(`${API_BASE}/notes/${id}`);

export const fetchNotes = (query = "") =>
  axios.get(`${API_BASE}/notes`, { params: query ? { q: query } : {} });

export const fetchNote = (id) => axios.get(`${API_BASE}/notes/${id}`);

export const exportUrl = (id, format) => `${API_BASE}/notes/${id}/export/${format}`;