const express = require("express");
const { registrar, iniciarSesion, recuperarContrasena } = require("../controllers/authController");

const router = express.Router();
router.post("/registro", registrar);
router.post("/login", iniciarSesion);
router.post("/recuperar", recuperarContrasena);

module.exports = router;
