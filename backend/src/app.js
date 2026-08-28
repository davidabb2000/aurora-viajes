const express = require("express");
const cors = require("cors");
const authRoutes = require("./routes/authRoutes");
const userRoutes = require("./routes/userRoutes");
const catalogRoutes = require("./routes/catalogRoutes");
const profileRoutes = require("./routes/profileRoutes");
const reservationRoutes = require("./routes/reservationRoutes");
const contactRoutes = require("./routes/contactRoutes");

const app = express();
app.use(cors({ origin: process.env.FRONTEND_URL || "http://localhost:5173" }));
app.use(express.json({ limit: "10kb" }));

app.get("/api/health", (_req, res) => res.json({ estado: "ok" }));
app.use("/api/auth", authRoutes);
app.use("/api/usuarios", userRoutes);
app.use("/api/catalogo", catalogRoutes);
app.use("/api/perfil", profileRoutes);
app.use("/api/reservas", reservationRoutes);
app.use("/api/contacto", contactRoutes);

app.use((error, _req, res, _next) => {
  console.error(error);
  res.status(500).json({ mensaje: "Error interno del servidor." });
});

module.exports = app;
