const jwt = require("jsonwebtoken");

function autenticar(req, res, next) {
  const encabezado = req.headers.authorization || "";
  const token = encabezado.startsWith("Bearer ") ? encabezado.slice(7) : null;
  if (!token) return res.status(401).json({ mensaje: "Se requiere un token JWT." });

  try {
    req.usuario = jwt.verify(token, process.env.JWT_SECRET || "cambia-esta-clave-en-produccion");
    next();
  } catch {
    return res.status(401).json({ mensaje: "El token no es válido o expiró." });
  }
}

function exigirRoles(...roles) {
  return (req, res, next) => {
    if (!roles.includes(req.usuario.rol)) return res.status(403).json({ mensaje: "No tienes permisos para esta acción." });
    next();
  };
}

module.exports = { autenticar, exigirRoles };
