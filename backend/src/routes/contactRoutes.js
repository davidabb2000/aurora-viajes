const express = require("express");
const pool = require("../config/db");
const { autenticar, exigirRoles } = require("../middleware/auth");

const router = express.Router();

router.post("/", async (req, res) => {
  const { nombre, correo, mensaje } = req.body || {};
  if (![nombre, correo, mensaje].every((valor) => typeof valor === "string" && valor.trim())) {
    return res.status(400).json({ mensaje: "Nombre, correo y mensaje son obligatorios." });
  }
  if (nombre.trim().length > 80 || correo.trim().length > 100 || mensaje.trim().length > 2000 ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(correo.trim())) {
    return res.status(400).json({ mensaje: "Revisa los datos del mensaje." });
  }

  const [resultado] = await pool.execute(
    "INSERT INTO mensajes_contacto (nombre, correo, mensaje) VALUES (?, ?, ?)",
    [nombre.trim(), correo.trim().toLowerCase(), mensaje.trim()]
  );
  res.status(201).json({ id: resultado.insertId, mensaje: "Mensaje recibido correctamente." });
});

router.get("/", autenticar, exigirRoles("administrador"), async (_req, res) => {
  const [mensajes] = await pool.execute(
    `SELECT id, nombre, correo, mensaje, creado_en AS creadoEn
     FROM mensajes_contacto ORDER BY creado_en DESC`
  );
  res.json(mensajes);
});

module.exports = router;