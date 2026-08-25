const express = require("express");
const bcrypt = require("bcrypt");
const pool = require("../config/db");
const { autenticar, exigirRoles } = require("../middleware/auth");

const router = express.Router();
router.use(autenticar, exigirRoles("administrador"));

router.post("/", async (req, res) => {
  const { nombre, apellido, tipoDocumento, numeroDocumento, direccion, telefono, correo, contrasena, rol = "cliente" } = req.body || {};
  if (![nombre, apellido, tipoDocumento, numeroDocumento, direccion, telefono, correo, contrasena].every((valor) => typeof valor === "string" && valor.trim())) {
    return res.status(400).json({ mensaje: "Todos los campos del usuario son obligatorios." });
  }
  if (!/^\d{6,12}$/.test(numeroDocumento) || !/^\d{7,10}$/.test(telefono) || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(correo) || !/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$/.test(contrasena)) {
    return res.status(400).json({ mensaje: "Revisa documento, teléfono, correo y contraseña." });
  }
  if (!["administrador", "empleado", "cliente"].includes(rol)) return res.status(400).json({ mensaje: "Rol no válido." });
  const hash = await bcrypt.hash(contrasena, 12);
  try {
    const [resultado] = await pool.execute(
      `INSERT INTO usuarios (nombre, apellido, tipo_documento, numero_documento, direccion, telefono, correo, contrasena_hash, rol_id)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, (SELECT id FROM roles WHERE nombre = ?))`,
      [nombre.trim(), apellido.trim(), tipoDocumento, numeroDocumento, direccion.trim(), telefono, correo.trim().toLowerCase(), hash, rol]
    );
    res.status(201).json({ id: resultado.insertId, mensaje: "Usuario creado correctamente." });
  } catch (error) {
    if (error.code === "ER_DUP_ENTRY") return res.status(409).json({ mensaje: "El correo o documento ya está registrado." });
    throw error;
  }
});

router.get("/", async (_req, res) => {
  const [usuarios] = await pool.execute(
    `SELECT u.id, u.nombre, u.apellido, u.tipo_documento AS tipoDocumento,
      u.numero_documento AS numeroDocumento, u.direccion, u.telefono, u.correo,
      u.activo, r.nombre AS rol FROM usuarios u JOIN roles r ON r.id = u.rol_id ORDER BY u.id DESC`
  );
  res.json(usuarios);
});

router.put("/:id", async (req, res) => {
  const { nombre, apellido, direccion, telefono } = req.body;
  if (![nombre, apellido, direccion, telefono].every(Boolean)) {
    return res.status(400).json({ mensaje: "Nombre, apellido, dirección y teléfono son obligatorios." });
  }
  const [resultado] = await pool.execute(
    "UPDATE usuarios SET nombre = ?, apellido = ?, direccion = ?, telefono = ? WHERE id = ?",
    [nombre.trim(), apellido.trim(), direccion.trim(), telefono, req.params.id]
  );
  if (!resultado.affectedRows) return res.status(404).json({ mensaje: "Usuario no encontrado." });
  res.json({ mensaje: "Usuario actualizado." });
});

router.patch("/:id/estado", async (req, res) => {
  const activo = Boolean(req.body.activo);
  const [resultado] = await pool.execute("UPDATE usuarios SET activo = ? WHERE id = ?", [activo, req.params.id]);
  if (!resultado.affectedRows) return res.status(404).json({ mensaje: "Usuario no encontrado." });
  res.json({ mensaje: "Estado actualizado." });
});

router.delete("/:id", async (req, res) => {
  const [resultado] = await pool.execute("DELETE FROM usuarios WHERE id = ?", [req.params.id]);
  if (!resultado.affectedRows) return res.status(404).json({ mensaje: "Usuario no encontrado." });
  res.status(204).send();
});

module.exports = router;
