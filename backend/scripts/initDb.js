const fs = require("fs");
const path = require("path");
const mysql = require("mysql2/promise");
const dotenv = require("dotenv");

dotenv.config({ path: path.resolve(__dirname, "../.env") });
dotenv.config({ path: path.resolve(__dirname, "../src/.env") });

async function inicializar() {
  const conexion = await mysql.createConnection({
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT || 3306),
    user: process.env.DB_USER || "root",
    password: process.env.DB_PASSWORD || "",
    multipleStatements: true,
  });
  const esquema = fs.readFileSync(path.resolve(__dirname, "../sql/schema.sql"), "utf8");
  await conexion.query(esquema);
  await conexion.end();
  console.log("Base de datos y tablas creadas correctamente.");
}

inicializar().catch((error) => {
  console.error(`${error.code || "DB_ERROR"}: ${error.message}`);
  process.exitCode = 1;
});
