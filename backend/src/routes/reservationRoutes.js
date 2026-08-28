const express = require("express");
const pool = require("../config/db");
const { autenticar, exigirRoles } = require("../middleware/auth");

const router = express.Router();

function datosReserva(body = {}) {
  const { destino, fechaSalida, fechaRegreso, pasajeros = 1, telefonoContacto, notas = "" } = body;
  const cantidad = Number(pasajeros);
  if (!destino || !/^\d{4}-\d{2}-\d{2}$/.test(fechaSalida || "") || !/^\d{4}-\d{2}-\d{2}$/.test(fechaRegreso || "") ||
      !Number.isInteger(cantidad) || cantidad < 1 || cantidad > 9 || !/^\d{7,10}$/.test(telefonoContacto || "") || notas.length > 300) {
    return null;
  }
  if (new Date(fechaRegreso) < new Date(fechaSalida)) return null;
  return [destino.trim(), fechaSalida, fechaRegreso, cantidad, telefonoContacto, notas.trim()];
}

router.post("/", autenticar, async (req, res) => {
  const datos = datosReserva(req.body);
  if (!datos) return res.status(400).json({ mensaje: "Revisa destino, fechas, pasajeros y teléfono de contacto." });
  const [resultado] = await pool.execute(
    `INSERT INTO reservas (usuario_id, destino, fecha_salida, fecha_regreso, pasajeros, telefono_contacto, notas)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [req.usuario.id, ...datos]
  );
  res.status(201).json({ id: resultado.insertId, mensaje: "Reserva creada correctamente." });
});

router.get("/mias", autenticar, async (req, res) => {
  const [reservas] = await pool.execute(
    `SELECT id, destino, fecha_salida AS fechaSalida, fecha_regreso AS fechaRegreso,
      pasajeros, telefono_contacto AS telefonoContacto, notas, estado
     FROM reservas WHERE usuario_id = ? ORDER BY fecha_salida DESC`,
    [req.usuario.id]
  );
  res.json(reservas);
});

router.get("/", autenticar, exigirRoles("administrador", "empleado"), async (_req, res) => {
  const [reservas] = await pool.execute(
    `SELECT r.id, r.destino, r.fecha_salida AS fechaSalida, r.fecha_regreso AS fechaRegreso,
      r.pasajeros, r.telefono_contacto AS telefonoContacto, r.notas, r.estado,
      CONCAT(u.nombre, ' ', u.apellido) AS cliente
     FROM reservas r JOIN usuarios u ON u.id = r.usuario_id ORDER BY r.creado_en DESC`
  );
  res.json(reservas);
});

router.put("/:id", autenticar, exigirRoles("administrador", "empleado"), async (req, res) => {
  const datos = datosReserva(req.body);
  if (!datos) return res.status(400).json({ mensaje: "Revisa destino, fechas, pasajeros y teléfono de contacto." });
  const [resultado] = await pool.execute(
    `UPDATE reservas
     SET destino = ?, fecha_salida = ?, fecha_regreso = ?, pasajeros = ?, telefono_contacto = ?, notas = ?
     WHERE id = ?`,
    [...datos, req.params.id]
  );
  if (!resultado.affectedRows) return res.status(404).json({ mensaje: "Reserva no encontrada." });
  res.json({ mensaje: "Solicitud actualizada correctamente." });
});

router.patch("/:id/estado", autenticar, exigirRoles("administrador", "empleado"), async (req, res) => {
  const estados = ["pendiente", "confirmada", "cancelada"];
  if (!estados.includes(req.body.estado)) return res.status(400).json({ mensaje: "Estado de reserva no válido." });
  const [resultado] = await pool.execute("UPDATE reservas SET estado = ? WHERE id = ?", [req.body.estado, req.params.id]);
  if (!resultado.affectedRows) return res.status(404).json({ mensaje: "Reserva no encontrada." });
  res.json({ mensaje: "Estado de reserva actualizado." });
});

router.delete("/:id", autenticar, async (req, res) => {
  const [resultado] = await pool.execute(
    "DELETE FROM reservas WHERE id = ? AND (usuario_id = ? OR EXISTS (SELECT 1 FROM usuarios WHERE id = ? AND rol_id = (SELECT id FROM roles WHERE nombre = 'administrador'))) ",
    [req.params.id, req.usuario.id, req.usuario.id]
  );
  if (!resultado.affectedRows) return res.status(404).json({ mensaje: "Reserva no encontrada." });
  res.status(204).send();
});

module.exports = router;
