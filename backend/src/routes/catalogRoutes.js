const express = require("express");
const pool = require("../config/db");
const { autenticar, exigirRoles } = require("../middleware/auth");

const router = express.Router();
const tablas = { productos: "productos", servicios: "servicios" };

function tablaSolicitada(req, res) {
  const tabla = tablas[req.params.entidad];
  if (!tabla) {
    res.status(404).json({ mensaje: "Entidad no encontrada." });
    return null;
  }
  return tabla;
}

router.get("/:entidad", async (req, res) => {
  const tabla = tablaSolicitada(req, res);
  if (!tabla) return;
  const [filas] = await pool.query(`SELECT id, nombre, descripcion, precio, activo FROM ${tabla} ORDER BY id DESC`);
  res.json(filas);
});

router.post("/:entidad", autenticar, exigirRoles("administrador"), async (req, res) => {
  const tabla = tablaSolicitada(req, res);
  if (!tabla) return;
  const { nombre, descripcion = "", precio = 0 } = req.body;
  if (!nombre || Number.isNaN(Number(precio)) || Number(precio) < 0) {
    return res.status(400).json({ mensaje: "Nombre y precio válido son obligatorios." });
  }
  const [resultado] = await pool.execute(
    `INSERT INTO ${tabla} (nombre, descripcion, precio) VALUES (?, ?, ?)`,
    [nombre.trim(), descripcion.trim(), Number(precio)]
  );
  res.status(201).json({ id: resultado.insertId, mensaje: "Registro creado." });
});

router.put("/:entidad/:id", autenticar, exigirRoles("administrador"), async (req, res) => {
  const tabla = tablaSolicitada(req, res);
  if (!tabla) return;
  const { nombre, descripcion = "", precio = 0, activo = true } = req.body;
  if (!nombre || Number.isNaN(Number(precio)) || Number(precio) < 0) {
    return res.status(400).json({ mensaje: "Nombre y precio válido son obligatorios." });
  }
  const [resultado] = await pool.execute(
    `UPDATE ${tabla} SET nombre = ?, descripcion = ?, precio = ?, activo = ? WHERE id = ?`,
    [nombre.trim(), descripcion.trim(), Number(precio), Boolean(activo), req.params.id]
  );
  if (!resultado.affectedRows) return res.status(404).json({ mensaje: "Registro no encontrado." });
  res.json({ mensaje: "Registro actualizado." });
});

router.delete("/:entidad/:id", autenticar, exigirRoles("administrador"), async (req, res) => {
  const tabla = tablaSolicitada(req, res);
  if (!tabla) return;
  const [resultado] = await pool.execute(`DELETE FROM ${tabla} WHERE id = ?`, [req.params.id]);
  if (!resultado.affectedRows) return res.status(404).json({ mensaje: "Registro no encontrado." });
  res.status(204).send();
});

module.exports = router;
