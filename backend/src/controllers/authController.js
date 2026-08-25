const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");
const pool = require("../config/db");

const JWT_SECRET = process.env.JWT_SECRET || "cambia-esta-clave-en-produccion";
const correoValido = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const telefonoValido = /^\d{7,10}$/;
const documentoValido = /^\d{6,12}$/;
const nombreValido = /^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]{2,40}$/;

function crearToken(usuario) {
  return jwt.sign({ id: usuario.id, rol: usuario.rol }, JWT_SECRET, { expiresIn: "2h" });
}

function respuestaUsuario(usuario) {
  return {
    id: usuario.id,
    nombre: usuario.nombre,
    apellido: usuario.apellido,
    correo: usuario.correo,
    rol: usuario.rol,
    activo: Boolean(usuario.activo),
  };
}

async function registrar(req, res) {
  const {
    nombre, apellido, tipoDocumento, numeroDocumento, direccion,
    telefono, correo, contrasena,
  } = req.body;

  if (![nombre, apellido, tipoDocumento, numeroDocumento, direccion, telefono, correo, contrasena].every(Boolean)) {
    return res.status(400).json({ mensaje: "Todos los campos son obligatorios." });
  }
  if (!nombreValido.test(nombre.trim()) || !nombreValido.test(apellido.trim())) {
    return res.status(400).json({ mensaje: "Nombre y apellido solo deben contener letras y tener entre 2 y 40 caracteres." });
  }
  if (!documentoValido.test(numeroDocumento) || !telefonoValido.test(telefono) || !correoValido.test(correo.trim())) {
    return res.status(400).json({ mensaje: "Revisa el formato del documento, teléfono y correo." });
  }
  if (direccion.trim().length < 5 || direccion.trim().length > 80 || tipoDocumento.length > 5 || correo.trim().length > 60) {
    return res.status(400).json({ mensaje: "Revisa la longitud de los datos ingresados." });
  }
  if (contrasena.length < 8 || contrasena.length > 20) {
    return res.status(400).json({ mensaje: "La contraseña debe tener entre 8 y 20 caracteres." });
  }

  try {
    const [existentes] = await pool.execute(
      "SELECT id FROM usuarios WHERE correo = ? OR numero_documento = ? LIMIT 1",
      [correo.trim().toLowerCase(), numeroDocumento]
    );
    if (existentes.length) return res.status(409).json({ mensaje: "El correo o documento ya está registrado." });

    const hash = await bcrypt.hash(contrasena, 12);
    await pool.execute(
      `INSERT INTO usuarios
       (nombre, apellido, tipo_documento, numero_documento, direccion, telefono, correo, contrasena_hash, rol_id)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, (SELECT id FROM roles WHERE nombre = 'cliente'))`,
      [nombre.trim(), apellido.trim(), tipoDocumento, numeroDocumento, direccion.trim(), telefono, correo.trim().toLowerCase(), hash]
    );
    return res.status(201).json({ mensaje: "Cuenta creada correctamente." });
  } catch (error) {
    console.error(error);
    return res.status(500).json({ mensaje: "No fue posible crear la cuenta." });
  }
}

async function iniciarSesion(req, res) {
  const { correo, contrasena } = req.body;
  if (!correo || !contrasena) return res.status(400).json({ mensaje: "Correo y contraseña son obligatorios." });

  try {
    const [filas] = await pool.execute(
      `SELECT u.*, r.nombre AS rol FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE u.correo = ? LIMIT 1`,
      [correo.trim().toLowerCase()]
    );
    const usuario = filas[0];
    if (!usuario || !usuario.activo || !(await bcrypt.compare(contrasena, usuario.contrasena_hash))) {
      return res.status(401).json({ mensaje: "Credenciales inválidas o usuario inactivo." });
    }
    return res.json({ token: crearToken(usuario), usuario: respuestaUsuario(usuario) });
  } catch (error) {
    console.error(error);
    return res.status(500).json({ mensaje: "No fue posible iniciar sesión." });
  }
}

async function recuperarContrasena(req, res) {
  const correo = typeof req.body?.correo === "string" ? req.body.correo.trim().toLowerCase() : "";
  if (!correo || !correoValido.test(correo)) return res.status(400).json({ mensaje: "Ingresa un correo electrónico válido." });
  try {
    await pool.execute("SELECT id FROM usuarios WHERE correo = ? LIMIT 1", [correo]);
    return res.json({ mensaje: "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña." });
  } catch (error) {
    console.error(error);
    return res.status(500).json({ mensaje: "No fue posible procesar la solicitud." });
  }
}

module.exports = { registrar, iniciarSesion, recuperarContrasena };
