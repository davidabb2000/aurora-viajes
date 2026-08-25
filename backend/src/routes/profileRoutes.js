const express = require("express");
const pool = require("../config/db");
const { autenticar } = require("../middleware/auth");

const router = express.Router();
router.use(autenticar);

router.get("/", async (req, res) => {
  try {
    const [filas] = await pool.execute(
      `SELECT id, nombre, apellido, direccion, telefono, correo
       FROM usuarios WHERE id = ? LIMIT 1`,
      [req.usuario.id]
    );
    if (!filas[0]) return res.status(404).json({ mensaje: "Usuario no encontrado." });
    res.json(filas[0]);
  } catch (error) {
    console.error("Error al consultar perfil:", error);
    res.status(500).json({ mensaje: "No fue posible consultar tus datos." });
  }
});

router.put("/", async (req, res) => {
  const { nombre, apellido, direccion, telefono } = req.body || {};
  if (![nombre, apellido, direccion, telefono].every((valor) => typeof valor === "string" && valor.trim())) {
    return res.status(400).json({ mensaje: "Todos los campos son obligatorios." });
  }
  if (nombre.trim().length > 40 || apellido.trim().length > 40 || direccion.trim().length > 80 || !/^\d{7,10}$/.test(telefono)) {
    return res.status(400).json({ mensaje: "Revisa la longitud y el formato de tus datos." });
  }
  try {
    const [resultado] = await pool.execute(
      "UPDATE usuarios SET nombre = ?, apellido = ?, direccion = ?, telefono = ? WHERE id = ?",
      [nombre.trim(), apellido.trim(), direccion.trim(), telefono, req.usuario.id]
    );
    if (!resultado.affectedRows) {
      const [usuario] = await pool.execute("SELECT id FROM usuarios WHERE id = ?", [req.usuario.id]);
      if (!usuario[0]) return res.status(404).json({ mensaje: "Usuario no encontrado." });
    }
    res.json({ id: req.usuario.id, nombre: nombre.trim(), apellido: apellido.trim(), direccion: direccion.trim(), telefono, mensaje: "Datos actualizados." });
  } catch (error) {
    console.error("Error al actualizar perfil:", error);
    res.status(500).json({ mensaje: "No fue posible actualizar tus datos." });
  }
});

module.exports = router;
