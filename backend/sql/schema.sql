-- Generado por scripts/exportar_esquema.py a partir de app/models/dominio.py. No editar a mano.
-- Solo estructura: el catálogo, los roles y el administrador los siembra la aplicación al arrancar.
CREATE DATABASE IF NOT EXISTS aurora_viajes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE aurora_viajes;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS detalle_facturas;
DROP TABLE IF EXISTS facturas;
DROP TABLE IF EXISTS detalle_ventas;
DROP TABLE IF EXISTS ventas;
DROP TABLE IF EXISTS reserva_excursiones;
DROP TABLE IF EXISTS reservas;
DROP TABLE IF EXISTS paquete_excursiones;
DROP TABLE IF EXISTS paquetes;
DROP TABLE IF EXISTS mensajes;
DROP TABLE IF EXISTS vuelos;
DROP TABLE IF EXISTS pqr;
DROP TABLE IF EXISTS hoteles;
DROP TABLE IF EXISTS excursiones;
DROP TABLE IF EXISTS destinos;
DROP TABLE IF EXISTS conversaciones;
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS rol_permisos;
DROP TABLE IF EXISTS ciudades;
DROP TABLE IF EXISTS tipos_documento;
DROP TABLE IF EXISTS servicios;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS productos;
DROP TABLE IF EXISTS permisos;
DROP TABLE IF EXISTS paises;
DROP TABLE IF EXISTS modelos_avion;
DROP TABLE IF EXISTS metodos_pago;
DROP TABLE IF EXISTS mensajes_contacto;
DROP TABLE IF EXISTS estados_reserva;
DROP TABLE IF EXISTS estados_pago;
DROP TABLE IF EXISTS aerolineas;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE aerolineas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(4) NOT NULL, 
	nombre VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	UNIQUE (nombre)
);

CREATE TABLE estados_pago (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(30) NOT NULL, 
	nombre VARCHAR(40) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);

CREATE TABLE estados_reserva (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(30) NOT NULL, 
	nombre VARCHAR(40) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);

CREATE TABLE mensajes_contacto (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(80) NOT NULL, 
	correo VARCHAR(100) NOT NULL, 
	mensaje TEXT NOT NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE metodos_pago (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(30) NOT NULL, 
	nombre VARCHAR(40) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);

CREATE TABLE modelos_avion (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(80) NOT NULL, 
	capacidad INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_modelo_capacidad CHECK (capacidad >= 1), 
	UNIQUE (nombre)
);

CREATE TABLE paises (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
);

CREATE TABLE permisos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
);

CREATE TABLE productos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(100) NOT NULL, 
	descripcion TEXT, 
	precio NUMERIC(12, 2) NOT NULL, 
	activo BOOL NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE roles (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(30) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
);

CREATE TABLE servicios (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(100) NOT NULL, 
	descripcion TEXT, 
	precio NUMERIC(12, 2) NOT NULL, 
	activo BOOL NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE tipos_documento (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(5) NOT NULL, 
	nombre VARCHAR(40) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);

CREATE TABLE ciudades (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	pais_id INTEGER NOT NULL, 
	nombre VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ciudad_pais_nombre UNIQUE (pais_id, nombre), 
	FOREIGN KEY(pais_id) REFERENCES paises (id)
);
CREATE INDEX ix_ciudades_pais_id ON ciudades (pais_id);

CREATE TABLE rol_permisos (
	rol_id INTEGER NOT NULL, 
	permiso_id INTEGER NOT NULL, 
	PRIMARY KEY (rol_id, permiso_id), 
	FOREIGN KEY(rol_id) REFERENCES roles (id), 
	FOREIGN KEY(permiso_id) REFERENCES permisos (id)
);

CREATE TABLE usuarios (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(40) NOT NULL, 
	apellido VARCHAR(40) NOT NULL, 
	tipo_documento_id INTEGER NOT NULL, 
	numero_documento VARCHAR(12) NOT NULL, 
	direccion VARCHAR(80) NOT NULL, 
	telefono VARCHAR(10) NOT NULL, 
	correo VARCHAR(60) NOT NULL, 
	contrasena_hash VARCHAR(255) NOT NULL, 
	activo BOOL NOT NULL, 
	rol_id INTEGER NOT NULL, 
	sesion_version INTEGER NOT NULL DEFAULT 0, 
	debe_cambiar_contrasena BOOL NOT NULL DEFAULT 0, 
	acepto_datos_en DATETIME, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tipo_documento_id) REFERENCES tipos_documento (id), 
	FOREIGN KEY(rol_id) REFERENCES roles (id)
);
CREATE UNIQUE INDEX ix_usuarios_correo ON usuarios (correo);
CREATE UNIQUE INDEX ix_usuarios_numero_documento ON usuarios (numero_documento);

CREATE TABLE conversaciones (
	id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT, 
	cliente_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES usuarios (id) ON DELETE SET NULL
);
CREATE INDEX ix_conversaciones_cliente_id ON conversaciones (cliente_id);

CREATE TABLE destinos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	ciudad_id INTEGER NOT NULL, 
	descripcion TEXT, 
	precio_base NUMERIC(12, 2) NOT NULL, 
	imagen_slug VARCHAR(80), 
	activo BOOL NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_destino_precio CHECK (precio_base >= 0), 
	UNIQUE (ciudad_id), 
	FOREIGN KEY(ciudad_id) REFERENCES ciudades (id)
);

CREATE TABLE excursiones (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(120) NOT NULL, 
	ciudad_id INTEGER NOT NULL, 
	duracion_horas INTEGER NOT NULL, 
	precio NUMERIC(12, 2) NOT NULL, 
	descripcion TEXT, 
	activo BOOL NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_excursion_ciudad_nombre UNIQUE (ciudad_id, nombre), 
	CONSTRAINT ck_excursion_duracion CHECK (duracion_horas >= 1 AND duracion_horas <= 48), 
	CONSTRAINT ck_excursion_precio CHECK (precio >= 0), 
	FOREIGN KEY(ciudad_id) REFERENCES ciudades (id)
);
CREATE INDEX ix_excursiones_ciudad_id ON excursiones (ciudad_id);

CREATE TABLE hoteles (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(120) NOT NULL, 
	ciudad_id INTEGER NOT NULL, 
	estrellas INTEGER NOT NULL, 
	precio_noche NUMERIC(12, 2) NOT NULL, 
	descripcion TEXT, 
	activo BOOL NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_hotel_ciudad_nombre UNIQUE (ciudad_id, nombre), 
	CONSTRAINT ck_hotel_estrellas CHECK (estrellas >= 1 AND estrellas <= 5), 
	CONSTRAINT ck_hotel_precio CHECK (precio_noche >= 0), 
	FOREIGN KEY(ciudad_id) REFERENCES ciudades (id)
);
CREATE INDEX ix_hoteles_ciudad_id ON hoteles (ciudad_id);

CREATE TABLE pqr (
	id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT, 
	cliente_id INTEGER NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	asunto VARCHAR(140) NOT NULL, 
	descripcion TEXT NOT NULL, 
	respuesta TEXT, 
	estado VARCHAR(30) NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES usuarios (id)
);
CREATE INDEX ix_pqr_cliente_id ON pqr (cliente_id);
CREATE INDEX ix_pqr_estado ON pqr (estado);

CREATE TABLE vuelos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	numero_vuelo VARCHAR(20) NOT NULL, 
	aerolinea_id INTEGER NOT NULL, 
	modelo_avion_id INTEGER NOT NULL, 
	origen_id INTEGER NOT NULL, 
	destino_id INTEGER NOT NULL, 
	fecha_salida DATETIME NOT NULL, 
	fecha_llegada DATETIME NOT NULL, 
	capacidad_maxima INTEGER NOT NULL, 
	puerta VARCHAR(10), 
	terminal VARCHAR(20), 
	estado VARCHAR(20) NOT NULL, 
	activo BOOL NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_vuelo_numero_fecha UNIQUE (numero_vuelo, fecha_salida), 
	CONSTRAINT ck_vuelo_ruta CHECK (origen_id <> destino_id), 
	CONSTRAINT ck_vuelo_horario CHECK (fecha_llegada > fecha_salida), 
	CONSTRAINT ck_vuelo_capacidad CHECK (capacidad_maxima >= 1), 
	FOREIGN KEY(aerolinea_id) REFERENCES aerolineas (id), 
	FOREIGN KEY(modelo_avion_id) REFERENCES modelos_avion (id), 
	FOREIGN KEY(origen_id) REFERENCES ciudades (id), 
	FOREIGN KEY(destino_id) REFERENCES ciudades (id)
);
CREATE INDEX ix_vuelos_aerolinea_id ON vuelos (aerolinea_id);
CREATE INDEX ix_vuelos_destino_id ON vuelos (destino_id);
CREATE INDEX ix_vuelos_fecha_salida ON vuelos (fecha_salida);
CREATE INDEX ix_vuelos_numero_vuelo ON vuelos (numero_vuelo);
CREATE INDEX ix_vuelos_origen_id ON vuelos (origen_id);

CREATE TABLE mensajes (
	id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT, 
	conversacion_id INTEGER UNSIGNED NOT NULL, 
	rol VARCHAR(20) NOT NULL, 
	contenido TEXT NOT NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversacion_id) REFERENCES conversaciones (id) ON DELETE CASCADE
);
CREATE INDEX ix_mensajes_conversacion_id ON mensajes (conversacion_id);

CREATE TABLE paquetes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(140) NOT NULL, 
	destino_id INTEGER NOT NULL, 
	vuelo_id INTEGER NOT NULL, 
	vuelo_regreso_id INTEGER, 
	hotel_id INTEGER NOT NULL, 
	noches INTEGER NOT NULL, 
	precio_base NUMERIC(12, 2) NOT NULL, 
	activo BOOL NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_paquete_noches CHECK (noches >= 1), 
	CONSTRAINT ck_paquete_precio CHECK (precio_base >= 0), 
	FOREIGN KEY(destino_id) REFERENCES destinos (id), 
	FOREIGN KEY(vuelo_id) REFERENCES vuelos (id), 
	FOREIGN KEY(vuelo_regreso_id) REFERENCES vuelos (id), 
	FOREIGN KEY(hotel_id) REFERENCES hoteles (id)
);

CREATE TABLE paquete_excursiones (
	paquete_id INTEGER NOT NULL, 
	excursion_id INTEGER NOT NULL, 
	PRIMARY KEY (paquete_id, excursion_id), 
	FOREIGN KEY(paquete_id) REFERENCES paquetes (id), 
	FOREIGN KEY(excursion_id) REFERENCES excursiones (id)
);

CREATE TABLE reservas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_id INTEGER NOT NULL, 
	creada_por_id INTEGER, 
	destino_id INTEGER NOT NULL, 
	vuelo_id INTEGER, 
	vuelo_regreso_id INTEGER, 
	paquete_id INTEGER, 
	hotel_id INTEGER, 
	fecha_salida DATE NOT NULL, 
	fecha_regreso DATE NOT NULL, 
	pasajeros INTEGER NOT NULL, 
	telefono_contacto VARCHAR(10) NOT NULL, 
	notas VARCHAR(300), 
	estado_id INTEGER NOT NULL, 
	estado_pago_id INTEGER NOT NULL, 
	metodo_pago_id INTEGER, 
	monto_total NUMERIC(12, 2) NOT NULL, 
	monto_vuelo NUMERIC(12, 2) NOT NULL, 
	monto_hotel NUMERIC(12, 2) NOT NULL, 
	monto_excursiones NUMERIC(12, 2) NOT NULL, 
	stripe_session_id VARCHAR(255), 
	pago_referencia VARCHAR(80), 
	pago_registrado_por_id INTEGER, 
	pagado_en DATETIME, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_reserva_pasajeros CHECK (pasajeros >= 1 AND pasajeros <= 9), 
	CONSTRAINT ck_reserva_fechas CHECK (fecha_regreso >= fecha_salida), 
	CONSTRAINT ck_reserva_monto CHECK (monto_vuelo >= 0 AND monto_hotel >= 0 AND monto_excursiones >= 0 AND ABS(monto_total - (monto_vuelo + monto_hotel + monto_excursiones)) < 0.005), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(creada_por_id) REFERENCES usuarios (id) ON DELETE SET NULL, 
	FOREIGN KEY(destino_id) REFERENCES destinos (id), 
	FOREIGN KEY(vuelo_id) REFERENCES vuelos (id), 
	FOREIGN KEY(vuelo_regreso_id) REFERENCES vuelos (id), 
	FOREIGN KEY(paquete_id) REFERENCES paquetes (id), 
	FOREIGN KEY(hotel_id) REFERENCES hoteles (id), 
	FOREIGN KEY(estado_id) REFERENCES estados_reserva (id), 
	FOREIGN KEY(estado_pago_id) REFERENCES estados_pago (id), 
	FOREIGN KEY(metodo_pago_id) REFERENCES metodos_pago (id), 
	FOREIGN KEY(pago_registrado_por_id) REFERENCES usuarios (id) ON DELETE SET NULL
);
CREATE INDEX ix_reservas_destino_id ON reservas (destino_id);
CREATE INDEX ix_reservas_hotel_id ON reservas (hotel_id);
CREATE INDEX ix_reservas_paquete_id ON reservas (paquete_id);
CREATE INDEX ix_reservas_usuario_id ON reservas (usuario_id);
CREATE INDEX ix_reservas_vuelo_id ON reservas (vuelo_id);
CREATE INDEX ix_reservas_vuelo_regreso_id ON reservas (vuelo_regreso_id);

CREATE TABLE reserva_excursiones (
	reserva_id INTEGER NOT NULL, 
	excursion_id INTEGER NOT NULL, 
	cantidad INTEGER NOT NULL, 
	precio_unitario NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (reserva_id, excursion_id), 
	CONSTRAINT ck_reserva_excursion_cantidad CHECK (cantidad >= 1), 
	CONSTRAINT ck_reserva_excursion_precio CHECK (precio_unitario >= 0), 
	FOREIGN KEY(reserva_id) REFERENCES reservas (id) ON DELETE CASCADE, 
	FOREIGN KEY(excursion_id) REFERENCES excursiones (id)
);

CREATE TABLE ventas (
	id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT, 
	cliente_id INTEGER NOT NULL, 
	usuario_id INTEGER, 
	reserva_id INTEGER, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	descuento NUMERIC(12, 2) NOT NULL, 
	impuestos NUMERIC(12, 2) NOT NULL, 
	total NUMERIC(12, 2) NOT NULL, 
	estado VARCHAR(30) NOT NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES usuarios (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	UNIQUE (reserva_id), 
	FOREIGN KEY(reserva_id) REFERENCES reservas (id) ON DELETE SET NULL
);
CREATE INDEX ix_ventas_cliente_id ON ventas (cliente_id);
CREATE INDEX ix_ventas_creado_en ON ventas (creado_en);
CREATE INDEX ix_ventas_estado ON ventas (estado);

CREATE TABLE detalle_ventas (
	id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT, 
	venta_id INTEGER UNSIGNED NOT NULL, 
	producto_id INTEGER, 
	servicio_id INTEGER, 
	nombre VARCHAR(140) NOT NULL, 
	cantidad INTEGER NOT NULL, 
	precio_unitario NUMERIC(12, 2) NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id) ON DELETE CASCADE, 
	FOREIGN KEY(producto_id) REFERENCES productos (id), 
	FOREIGN KEY(servicio_id) REFERENCES servicios (id)
);
CREATE INDEX ix_detalle_ventas_venta_id ON detalle_ventas (venta_id);

CREATE TABLE facturas (
	id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT, 
	venta_id INTEGER UNSIGNED NOT NULL, 
	numero VARCHAR(40) NOT NULL, 
	estado VARCHAR(30) NOT NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (venta_id), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ix_facturas_numero ON facturas (numero);

CREATE TABLE detalle_facturas (
	id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT, 
	factura_id INTEGER UNSIGNED NOT NULL, 
	nombre VARCHAR(140) NOT NULL, 
	cantidad INTEGER NOT NULL, 
	precio_unitario NUMERIC(12, 2) NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(factura_id) REFERENCES facturas (id) ON DELETE CASCADE
);
CREATE INDEX ix_detalle_facturas_factura_id ON detalle_facturas (factura_id);
