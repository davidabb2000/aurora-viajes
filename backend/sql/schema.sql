CREATE DATABASE IF NOT EXISTS aurora_viajes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE aurora_viajes;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS reservas;
DROP TABLE IF EXISTS paquete_excursiones;
DROP TABLE IF EXISTS paquetes;
DROP TABLE IF EXISTS excursiones;
DROP TABLE IF EXISTS hoteles;
DROP TABLE IF EXISTS vuelos;
DROP TABLE IF EXISTS mensajes_contacto;
DROP TABLE IF EXISTS detalle_ventas;
DROP TABLE IF EXISTS detalle_facturas;
DROP TABLE IF EXISTS mensajes;
DROP TABLE IF EXISTS conversaciones;
DROP TABLE IF EXISTS facturas;
DROP TABLE IF EXISTS ventas;
DROP TABLE IF EXISTS pqr;
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS productos;
DROP TABLE IF EXISTS servicios;
DROP TABLE IF EXISTS rol_permisos;
DROP TABLE IF EXISTS permisos;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS metodos_pago;
DROP TABLE IF EXISTS estados_pago;
DROP TABLE IF EXISTS estados_reserva;
DROP TABLE IF EXISTS destinos;
DROP TABLE IF EXISTS paises;
DROP TABLE IF EXISTS tipos_documento;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE roles (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE permisos (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE rol_permisos (
  rol_id INT UNSIGNED NOT NULL,
  permiso_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (rol_id, permiso_id),
  CONSTRAINT fk_rolpermiso_rol FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE CASCADE,
  CONSTRAINT fk_rolpermiso_permiso FOREIGN KEY (permiso_id) REFERENCES permisos(id) ON DELETE CASCADE
);

CREATE TABLE tipos_documento (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(5) NOT NULL UNIQUE,
  nombre VARCHAR(40) NOT NULL
);

CREATE TABLE paises (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE destinos (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  pais_id INT UNSIGNED NOT NULL,
  nombre VARCHAR(120) NOT NULL UNIQUE,
  descripcion TEXT,
  precio_base DECIMAL(12,2) NOT NULL DEFAULT 0,
  imagen_slug VARCHAR(80),
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_destino_pais FOREIGN KEY (pais_id) REFERENCES paises(id) ON DELETE RESTRICT
);

CREATE TABLE estados_reserva (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(30) NOT NULL UNIQUE,
  nombre VARCHAR(40) NOT NULL
);

CREATE TABLE estados_pago (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(30) NOT NULL UNIQUE,
  nombre VARCHAR(40) NOT NULL
);

CREATE TABLE metodos_pago (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(30) NOT NULL UNIQUE,
  nombre VARCHAR(40) NOT NULL
);

CREATE TABLE usuarios (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(40) NOT NULL,
  apellido VARCHAR(40) NOT NULL,
  tipo_documento_id INT UNSIGNED NOT NULL,
  numero_documento VARCHAR(12) NOT NULL UNIQUE,
  direccion VARCHAR(80) NOT NULL,
  telefono VARCHAR(10) NOT NULL,
  correo VARCHAR(60) NOT NULL UNIQUE,
  contrasena_hash VARCHAR(255) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  rol_id INT UNSIGNED NOT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_usuario_tipodoc FOREIGN KEY (tipo_documento_id) REFERENCES tipos_documento(id) ON DELETE RESTRICT,
  CONSTRAINT fk_usuario_rol FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE RESTRICT
);

CREATE TABLE productos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  descripcion TEXT,
  precio DECIMAL(12,2) NOT NULL DEFAULT 0,
  activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE servicios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  descripcion TEXT,
  precio DECIMAL(12,2) NOT NULL DEFAULT 0,
  activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE vuelos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  numero_vuelo VARCHAR(20) NOT NULL UNIQUE,
  aerolinea VARCHAR(80) NOT NULL,
  avion VARCHAR(80) NOT NULL,
  origen VARCHAR(120) NOT NULL,
  destino VARCHAR(120) NOT NULL,
  fecha_salida DATETIME NOT NULL,
  fecha_llegada DATETIME NOT NULL,
  capacidad_maxima SMALLINT UNSIGNED NOT NULL,
  puerta VARCHAR(10),
  terminal VARCHAR(20),
  estado VARCHAR(20) NOT NULL DEFAULT 'programado',
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT chk_vuelo_horario CHECK (fecha_llegada > fecha_salida),
  CONSTRAINT chk_vuelo_capacidad CHECK (capacidad_maxima BETWEEN 1 AND 1000)
);

CREATE TABLE hoteles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  ciudad VARCHAR(120) NOT NULL,
  pais VARCHAR(120) NOT NULL,
  estrellas TINYINT UNSIGNED NOT NULL,
  precio_noche DECIMAL(12,2) NOT NULL DEFAULT 0,
  descripcion TEXT,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT chk_hotel_estrellas CHECK (estrellas BETWEEN 1 AND 5),
  CONSTRAINT chk_hotel_precio CHECK (precio_noche >= 0)
);

CREATE TABLE excursiones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  ciudad VARCHAR(120) NOT NULL,
  pais VARCHAR(120) NOT NULL,
  duracion_horas SMALLINT UNSIGNED NOT NULL,
  precio DECIMAL(12,2) NOT NULL DEFAULT 0,
  descripcion TEXT,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT chk_excursion_duracion CHECK (duracion_horas BETWEEN 1 AND 48),
  CONSTRAINT chk_excursion_precio CHECK (precio >= 0)
);

CREATE TABLE paquetes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(140) NOT NULL,
  destino_id INT UNSIGNED NOT NULL,
  vuelo_id INT NOT NULL,
  hotel_id INT NOT NULL,
  fecha_salida DATE NOT NULL,
  fecha_regreso DATE NOT NULL,
  precio_base DECIMAL(12,2) NOT NULL DEFAULT 0,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_paquete_destino FOREIGN KEY (destino_id) REFERENCES destinos(id) ON DELETE RESTRICT,
  CONSTRAINT fk_paquete_vuelo FOREIGN KEY (vuelo_id) REFERENCES vuelos(id) ON DELETE RESTRICT,
  CONSTRAINT fk_paquete_hotel FOREIGN KEY (hotel_id) REFERENCES hoteles(id) ON DELETE RESTRICT,
  CONSTRAINT chk_paquete_fechas CHECK (fecha_regreso >= fecha_salida),
  CONSTRAINT chk_paquete_precio CHECK (precio_base >= 0)
);

CREATE TABLE paquete_excursiones (
  paquete_id INT NOT NULL,
  excursion_id INT NOT NULL,
  PRIMARY KEY (paquete_id, excursion_id),
  CONSTRAINT fk_paquete_excursion_paquete FOREIGN KEY (paquete_id) REFERENCES paquetes(id) ON DELETE CASCADE,
  CONSTRAINT fk_paquete_excursion_excursion FOREIGN KEY (excursion_id) REFERENCES excursiones(id) ON DELETE RESTRICT
);

CREATE TABLE reservas (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  usuario_id INT UNSIGNED NOT NULL,
  destino_id INT UNSIGNED NOT NULL,
  vuelo_id INT NULL,
  paquete_id INT NULL,
  fecha_salida DATE NOT NULL,
  fecha_regreso DATE NOT NULL,
  pasajeros TINYINT UNSIGNED NOT NULL DEFAULT 1,
  telefono_contacto VARCHAR(10) NOT NULL,
  notas VARCHAR(300),
  estado_id INT UNSIGNED NOT NULL,
  estado_pago_id INT UNSIGNED NOT NULL,
  metodo_pago_id INT UNSIGNED NULL,
  monto_total DECIMAL(12,2) NOT NULL DEFAULT 0,
  stripe_session_id VARCHAR(255),
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_reserva_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
  CONSTRAINT fk_reserva_destino FOREIGN KEY (destino_id) REFERENCES destinos(id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_vuelo FOREIGN KEY (vuelo_id) REFERENCES vuelos(id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_paquete FOREIGN KEY (paquete_id) REFERENCES paquetes(id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_estado FOREIGN KEY (estado_id) REFERENCES estados_reserva(id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_estado_pago FOREIGN KEY (estado_pago_id) REFERENCES estados_pago(id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_metodo_pago FOREIGN KEY (metodo_pago_id) REFERENCES metodos_pago(id) ON DELETE SET NULL
);

CREATE TABLE mensajes_contacto (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL,
  correo VARCHAR(100) NOT NULL,
  mensaje TEXT NOT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ventas (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT UNSIGNED NOT NULL,
  usuario_id INT UNSIGNED NULL,
  subtotal DECIMAL(12,2) NOT NULL DEFAULT 0,
  descuento DECIMAL(12,2) NOT NULL DEFAULT 0,
  impuestos DECIMAL(12,2) NOT NULL DEFAULT 0,
  total DECIMAL(12,2) NOT NULL DEFAULT 0,
  estado VARCHAR(30) NOT NULL DEFAULT 'completada',
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_venta_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE RESTRICT,
  CONSTRAINT fk_venta_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE detalle_ventas (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  venta_id INT UNSIGNED NOT NULL,
  producto_id INT NULL,
  servicio_id INT NULL,
  nombre VARCHAR(140) NOT NULL,
  cantidad INT UNSIGNED NOT NULL,
  precio_unitario DECIMAL(12,2) NOT NULL,
  subtotal DECIMAL(12,2) NOT NULL,
  CONSTRAINT fk_detalle_venta FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
  CONSTRAINT fk_detalle_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE RESTRICT,
  CONSTRAINT fk_detalle_servicio FOREIGN KEY (servicio_id) REFERENCES servicios(id) ON DELETE RESTRICT
);

CREATE TABLE facturas (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  venta_id INT UNSIGNED NOT NULL UNIQUE,
  numero VARCHAR(40) NOT NULL UNIQUE,
  estado VARCHAR(30) NOT NULL DEFAULT 'emitida',
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_factura_venta FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE
);

CREATE TABLE detalle_facturas (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  factura_id INT UNSIGNED NOT NULL,
  nombre VARCHAR(140) NOT NULL,
  cantidad INT UNSIGNED NOT NULL,
  precio_unitario DECIMAL(12,2) NOT NULL,
  subtotal DECIMAL(12,2) NOT NULL,
  CONSTRAINT fk_detalle_factura FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE
);

CREATE TABLE pqr (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT UNSIGNED NOT NULL,
  tipo VARCHAR(30) NOT NULL,
  asunto VARCHAR(140) NOT NULL,
  descripcion TEXT NOT NULL,
  respuesta TEXT,
  estado VARCHAR(30) NOT NULL DEFAULT 'pendiente',
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_pqr_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE conversaciones (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT UNSIGNED NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_conversacion_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE mensajes (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  conversacion_id INT UNSIGNED NOT NULL,
  rol VARCHAR(20) NOT NULL,
  contenido TEXT NOT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_mensaje_conversacion FOREIGN KEY (conversacion_id) REFERENCES conversaciones(id) ON DELETE CASCADE
);

INSERT INTO tipos_documento (codigo, nombre) VALUES
  ('CC', 'Cédula de ciudadanía'),
  ('TI', 'Tarjeta de identidad'),
  ('CE', 'Cédula de extranjería'),
  ('PA', 'Pasaporte')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO paises (nombre) VALUES
  ('Francia'),
  ('Japón'),
  ('Indonesia'),
  ('Colombia'),
  ('Grecia'),
  ('Perú'),
  ('Marruecos'),
  ('Islandia'),
  ('Estados Unidos'),
  ('Egipto')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO estados_reserva (codigo, nombre) VALUES
  ('pendiente', 'Pendiente'),
  ('confirmada', 'Confirmada'),
  ('cancelada', 'Cancelada')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO estados_pago (codigo, nombre) VALUES
  ('pendiente', 'Pendiente'),
  ('pagado', 'Pagado'),
  ('fallido', 'Fallido')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO metodos_pago (codigo, nombre) VALUES
  ('stripe', 'Stripe'),
  ('transferencia', 'Transferencia')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'París, Francia', 'Recorre el Sena al atardecer y descubre por qué la Ciudad Luz sigue inspirando a viajeros de todo el mundo.', 6900000, 'paris', TRUE
FROM paises p WHERE p.nombre = 'Francia'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'Kioto, Japón', 'Templos centenarios, jardines de piedra y la calma de los bosques de bambú te esperan en el antiguo Japón.', 8400000, 'kioto', TRUE
FROM paises p WHERE p.nombre = 'Japón'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'Bali, Indonesia', 'Playas volcánicas, arrozales en terraza y una cultura espiritual que transforma cada visita en un ritual.', 7600000, 'bali', TRUE
FROM paises p WHERE p.nombre = 'Indonesia'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'Cartagena, Colombia', 'Murallas coloniales, calles de colores y el Caribe a un paso: la joya histórica de Colombia.', 1200000, 'cartagena', TRUE
FROM paises p WHERE p.nombre = 'Colombia'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'Santorini, Grecia', 'Casas blancas suspendidas sobre el mar Egeo y atardeceres que se han vuelto leyenda.', 9800000, 'santorini', TRUE
FROM paises p WHERE p.nombre = 'Grecia'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'Cusco, Perú', 'Puerta de entrada a Machu Picchu y corazón del imperio inca, entre montañas y terrazas ancestrales.', 2500000, 'cusco', TRUE
FROM paises p WHERE p.nombre = 'Perú'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'Marrakech, Marruecos', 'Zocos bulliciosos, palacios ocultos y el aroma a especias en cada esquina de la medina.', 8900000, 'marrakech', TRUE
FROM paises p WHERE p.nombre = 'Marruecos'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'Reikiavik, Islandia', 'Auroras boreales, fuentes termales y paisajes volcánicos al borde del Atlántico Norte.', 10800000, 'reikiavik', TRUE
FROM paises p WHERE p.nombre = 'Islandia'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'Nueva York, EE. UU.', 'Rascacielos icónicos, parques urbanos y una energía que nunca duerme.', 7200000, 'nueva-york', TRUE
FROM paises p WHERE p.nombre = 'Estados Unidos'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO destinos (pais_id, nombre, descripcion, precio_base, imagen_slug, activo)
SELECT p.id, 'El Cairo, Egipto', 'Las pirámides de Giza y el Nilo milenario te acercan a una de las civilizaciones más fascinantes de la historia.', 9300000, 'cairo', TRUE
FROM paises p WHERE p.nombre = 'Egipto'
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion), precio_base = VALUES(precio_base), imagen_slug = VALUES(imagen_slug), activo = VALUES(activo);

INSERT INTO roles (nombre) VALUES ('administrador'), ('empleado'), ('cliente')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO permisos (nombre) VALUES
  ('usuarios:gestionar'),
  ('productos:gestionar'),
  ('servicios:gestionar'),
  ('reservas:gestionar'),
  ('reservas:crear'),
  ('mensajes:leer')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO rol_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r
JOIN permisos p ON (
  (r.nombre = 'administrador' AND p.nombre IN ('usuarios:gestionar','productos:gestionar','servicios:gestionar','reservas:gestionar','mensajes:leer')) OR
  (r.nombre = 'empleado' AND p.nombre IN ('reservas:gestionar')) OR
  (r.nombre = 'cliente' AND p.nombre IN ('reservas:crear'))
)
ON DUPLICATE KEY UPDATE permiso_id = VALUES(permiso_id);
