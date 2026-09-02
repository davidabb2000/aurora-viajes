from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import MensajeContacto, Permiso, Producto, Reserva, Role, Servicio, User
from app.schemas import (
    ContactoCreate,
    EstadoUpdate,
    ProductoCreate,
    ReservaCreate,
    ServicioCreate,
    UserCreate,
    UserLogin,
    UserOut,
    UsuarioCreateAdmin,
    UsuarioUpdate,
)
from app.security import create_access_token, get_current_user, hash_password, oauth2_scheme, verify_password

Base.metadata.create_all(bind=engine)

# Roles y permisos mínimos requeridos por la aplicación.
PERMISOS_POR_ROL = {
    "administrador": ["usuarios:gestionar", "productos:gestionar", "servicios:gestionar", "reservas:gestionar", "mensajes:leer"],
    "empleado": ["reservas:gestionar"],
    "cliente": ["reservas:crear"],
}


def seed_roles_y_permisos() -> None:
    db = SessionLocal()
    try:
        roles_cache = {}
        for nombre_rol in PERMISOS_POR_ROL:
            role = db.query(Role).filter(Role.nombre == nombre_rol).first()
            if not role:
                role = Role(nombre=nombre_rol)
                db.add(role)
                db.flush()
            roles_cache[nombre_rol] = role

        permisos_cache = {}
        for nombre_rol, permisos in PERMISOS_POR_ROL.items():
            for nombre_permiso in permisos:
                permiso = permisos_cache.get(nombre_permiso) or db.query(Permiso).filter(Permiso.nombre == nombre_permiso).first()
                if not permiso:
                    permiso = Permiso(nombre=nombre_permiso)
                    db.add(permiso)
                    db.flush()
                permisos_cache[nombre_permiso] = permiso
                if permiso not in roles_cache[nombre_rol].permisos:
                    roles_cache[nombre_rol].permisos.append(permiso)
        db.commit()
    finally:
        db.close()


def seed_admin_inicial() -> None:
    db = SessionLocal()
    try:
        admin_role = db.query(Role).filter(Role.nombre == "administrador").first()
        if not admin_role or db.query(User).filter(User.rol_id == admin_role.id).first():
            return
        admin = User(
            nombre="Administrador",
            apellido="Aurora",
            tipo_documento="CC",
            numero_documento="1000000000",
            direccion="Oficina principal Aurora Viajes",
            telefono="3000000000",
            correo=settings.ADMIN_EMAIL.lower(),
            contrasena_hash=hash_password(settings.ADMIN_PASSWORD),
            rol_id=admin_role.id,
            activo=True,
        )
        db.add(admin)
        db.commit()
        print(f"Usuario administrador inicial creado -> correo: {settings.ADMIN_EMAIL}")
    finally:
        db.close()


seed_roles_y_permisos()
seed_admin_inicial()

app = FastAPI(title="Aurora Viajes API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


@app.get("/api/health")
def health():
    return {"estado": "ok"}


@app.get("/api/usuarios", response_model=list[dict])
def list_users(db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    usuarios = (
        db.query(User, Role.nombre.label("rol"))
        .join(Role, User.rol_id == Role.id)
        .order_by(User.id.desc())
        .all()
    )
    return [
        {
            "id": user.id,
            "nombre": user.nombre,
            "apellido": user.apellido,
            "tipoDocumento": user.tipo_documento,
            "numeroDocumento": user.numero_documento,
            "direccion": user.direccion,
            "telefono": user.telefono,
            "correo": user.correo,
            "activo": user.activo,
            "rol": rol,
        }
        for user, rol in usuarios
    ]


@app.post("/api/usuarios/registro", status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter((User.correo == payload.correo.lower()) | (User.numero_documento == payload.numeroDocumento)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo o documento ya está registrado.")

    role = db.query(Role).filter(Role.nombre == "cliente").first()
    if not role:
        role = Role(nombre="cliente")
        db.add(role)
        db.commit()
        db.refresh(role)

    user = User(
        nombre=payload.nombre.strip(),
        apellido=payload.apellido.strip(),
        tipo_documento=payload.tipoDocumento,
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion.strip(),
        telefono=payload.telefono,
        correo=payload.correo.lower(),
        contrasena_hash=hash_password(payload.contrasena),
        rol_id=role.id,
        activo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"mensaje": "Cuenta creada correctamente."}


@app.post("/api/usuarios", status_code=status.HTTP_201_CREATED)
def create_user_admin(payload: UsuarioCreateAdmin, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    existing = db.query(User).filter((User.correo == payload.correo.lower()) | (User.numero_documento == payload.numeroDocumento)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo o documento ya está registrado.")
    role = db.query(Role).filter(Role.nombre == payload.rol).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol no válido.")

    user = User(
        nombre=payload.nombre.strip(),
        apellido=payload.apellido.strip(),
        tipo_documento=payload.tipoDocumento,
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion.strip(),
        telefono=payload.telefono,
        correo=payload.correo.lower(),
        contrasena_hash=hash_password(payload.contrasena),
        rol_id=role.id,
        activo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "mensaje": "Usuario creado correctamente."}


@app.post("/api/auth/login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).join(Role, User.rol_id == Role.id).filter(User.correo == payload.correo.lower()).first()
    if not user or not user.activo or not verify_password(payload.contrasena, user.contrasena_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas o usuario inactivo.")
    token = create_access_token(user)
    return {
        "token": token,
        "usuario": {
            "id": user.id,
            "nombre": user.nombre,
            "apellido": user.apellido,
            "correo": user.correo,
            "rol": user.role.nombre if user.role else "cliente",
            "activo": user.activo,
        },
    }


@app.post("/api/auth/recuperar")
def recover_password(payload: dict, db: Session = Depends(get_db)):
    correo = str(payload.get("correo", "")).strip().lower()
    if not correo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ingresa un correo electrónico válido.")
    user = db.query(User).filter(User.correo == correo).first()
    if not user:
        return {"mensaje": "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña."}
    token = create_access_token(user, purpose="recuperacion")
    return {
        "mensaje": "Se generó un enlace de recuperación válido para tu cuenta.",
        "token": token,
    }


@app.post("/api/auth/restablecer")
def reset_password(payload: dict, db: Session = Depends(get_db)):
    correo = str(payload.get("correo", "")).strip().lower()
    token = str(payload.get("token", "")).strip()
    nueva_contrasena = str(payload.get("nuevaContrasena", "")).strip()
    if not correo or not token or not nueva_contrasena:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Correo, token y nueva contraseña son obligatorios.")
    if len(nueva_contrasena) < 8 or len(nueva_contrasena) > 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña debe tener entre 8 y 20 caracteres.")
    try:
        decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El token de recuperación no es válido o expiró.") from exc

    if decoded.get("purpose") != "recuperacion":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El token no corresponde a recuperación de contraseña.")
    user = db.query(User).filter(User.id == decoded.get("id"), User.correo == correo).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado para este token.")
    user.contrasena_hash = hash_password(nueva_contrasena)
    db.commit()
    return {"mensaje": "Contraseña actualizada correctamente."}


@app.get("/api/usuarios/{usuario_id}")
def get_user(usuario_id: int, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    user = db.query(User).filter(User.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    return {
        "id": user.id,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "tipoDocumento": user.tipo_documento,
        "numeroDocumento": user.numero_documento,
        "direccion": user.direccion,
        "telefono": user.telefono,
        "correo": user.correo,
        "rol": user.role.nombre if user.role else "cliente",
        "activo": user.activo,
    }


@app.put("/api/usuarios/{usuario_id}")
def update_user(usuario_id: int, payload: UsuarioUpdate, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    user = db.query(User).filter(User.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    if payload.correo is not None or payload.numeroDocumento is not None:
        correo = payload.correo.lower() if payload.correo is not None else user.correo
        documento = payload.numeroDocumento if payload.numeroDocumento is not None else user.numero_documento
        duplicado = db.query(User).filter(
            User.id != usuario_id, (User.correo == correo) | (User.numero_documento == documento)
        ).first()
        if duplicado:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo o documento ya está registrado.")

    if payload.nombre is not None:
        user.nombre = payload.nombre.strip()
    if payload.apellido is not None:
        user.apellido = payload.apellido.strip()
    if payload.tipoDocumento is not None:
        user.tipo_documento = payload.tipoDocumento
    if payload.numeroDocumento is not None:
        user.numero_documento = payload.numeroDocumento
    if payload.direccion is not None:
        user.direccion = payload.direccion.strip()
    if payload.telefono is not None:
        user.telefono = payload.telefono
    if payload.correo is not None:
        user.correo = payload.correo.lower()
    if payload.rol is not None:
        role = db.query(Role).filter(Role.nombre == payload.rol).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol no válido.")
        user.rol_id = role.id

    db.commit()
    return {"mensaje": "Usuario actualizado."}


@app.patch("/api/usuarios/{usuario_id}/estado")
def update_user_status(usuario_id: int, payload: EstadoUpdate, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    user = db.query(User).filter(User.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    user.activo = payload.activo
    db.commit()
    return {"mensaje": "Estado actualizado."}


@app.delete("/api/usuarios/{usuario_id}")
def delete_user(usuario_id: int, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    user = db.query(User).filter(User.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    db.delete(user)
    db.commit()
    return {"mensaje": "Usuario eliminado."}


@app.get("/api/productos")
def list_products(db: Session = Depends(get_db)):
    productos = db.query(Producto).order_by(Producto.id.desc()).all()
    return [{"id": p.id, "nombre": p.nombre, "descripcion": p.descripcion, "precio": float(p.precio or 0), "activo": p.activo} for p in productos]


@app.get("/api/productos/{producto_id}")
def get_product(producto_id: int, db: Session = Depends(get_db)):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")
    return {"id": producto.id, "nombre": producto.nombre, "descripcion": producto.descripcion, "precio": float(producto.precio or 0), "activo": producto.activo}


@app.post("/api/productos")
def create_product(payload: ProductoCreate, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    product = Producto(nombre=payload.nombre, descripcion=payload.descripcion, precio=str(payload.precio), activo=payload.activo)
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": product.id, "mensaje": "Producto creado."}


@app.put("/api/productos/{producto_id}")
def update_product(producto_id: int, payload: ProductoCreate, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")
    producto.nombre = payload.nombre
    producto.descripcion = payload.descripcion
    producto.precio = str(payload.precio)
    producto.activo = payload.activo
    db.commit()
    return {"mensaje": "Producto actualizado."}


@app.delete("/api/productos/{producto_id}")
def delete_product(producto_id: int, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")
    db.delete(producto)
    db.commit()
    return {"mensaje": "Producto eliminado."}


@app.get("/api/servicios")
def list_services(db: Session = Depends(get_db)):
    servicios = db.query(Servicio).order_by(Servicio.id.desc()).all()
    return [{"id": s.id, "nombre": s.nombre, "descripcion": s.descripcion, "precio": float(s.precio or 0), "activo": s.activo} for s in servicios]


@app.get("/api/servicios/{servicio_id}")
def get_service(servicio_id: int, db: Session = Depends(get_db)):
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if not servicio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado.")
    return {"id": servicio.id, "nombre": servicio.nombre, "descripcion": servicio.descripcion, "precio": float(servicio.precio or 0), "activo": servicio.activo}


@app.post("/api/servicios")
def create_service(payload: ServicioCreate, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    service = Servicio(nombre=payload.nombre, descripcion=payload.descripcion, precio=str(payload.precio), activo=payload.activo)
    db.add(service)
    db.commit()
    db.refresh(service)
    return {"id": service.id, "mensaje": "Servicio creado."}


@app.put("/api/servicios/{servicio_id}")
def update_service(servicio_id: int, payload: ServicioCreate, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if not servicio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado.")
    servicio.nombre = payload.nombre
    servicio.descripcion = payload.descripcion
    servicio.precio = str(payload.precio)
    servicio.activo = payload.activo
    db.commit()
    return {"mensaje": "Servicio actualizado."}


@app.delete("/api/servicios/{servicio_id}")
def delete_service(servicio_id: int, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if not servicio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado.")
    db.delete(servicio)
    db.commit()
    return {"mensaje": "Servicio eliminado."}


@app.post("/api/reservas")
def create_reservation(payload: ReservaCreate, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    from datetime import datetime
    try:
        fecha_salida = datetime.strptime(payload.fechaSalida, "%Y-%m-%d").date()
        fecha_regreso = datetime.strptime(payload.fechaRegreso, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Fechas inválidas.") from exc
    if fecha_regreso < fecha_salida:
        raise HTTPException(status_code=400, detail="La fecha de regreso debe ser posterior a la fecha de salida.")
    reserva = Reserva(
        usuario_id=current_user.id,
        destino=payload.destino,
        fecha_salida=fecha_salida,
        fecha_regreso=fecha_regreso,
        pasajeros=payload.pasajeros,
        telefono_contacto=payload.telefonoContacto,
        notas=payload.notas,
        estado="pendiente",
    )
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return {"id": reserva.id, "mensaje": "Solicitud registrada."}


@app.get("/api/reservas")
def list_reservations(db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre not in {"administrador", "empleado"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    reservas = db.query(Reserva).order_by(Reserva.id.desc()).all()
    return [{
        "id": r.id,
        "cliente": f"{r.usuario.nombre} {r.usuario.apellido}",
        "destino": r.destino,
        "fechaSalida": r.fecha_salida.isoformat(),
        "fechaRegreso": r.fecha_regreso.isoformat(),
        "pasajeros": r.pasajeros,
        "telefonoContacto": r.telefono_contacto,
        "notas": r.notas,
        "estado": r.estado,
    } for r in reservas]


@app.get("/api/reservas/mias")
def user_reservations(db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    reservas = db.query(Reserva).filter(Reserva.usuario_id == current_user.id).order_by(Reserva.id.desc()).all()
    return [{
        "id": r.id,
        "destino": r.destino,
        "fechaSalida": r.fecha_salida.isoformat(),
        "fechaRegreso": r.fecha_regreso.isoformat(),
        "pasajeros": r.pasajeros,
        "telefonoContacto": r.telefono_contacto,
        "notas": r.notas,
        "estado": r.estado,
    } for r in reservas]


@app.patch("/api/reservas/{reserva_id}/estado")
def update_reservation_status(reserva_id: int, payload: dict, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre not in {"administrador", "empleado"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    reserva = db.query(Reserva).filter(Reserva.id == reserva_id).first()
    if not reserva:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada.")
    reserva.estado = payload.get("estado", reserva.estado)
    db.commit()
    return {"mensaje": "Estado actualizado."}


@app.delete("/api/reservas/{reserva_id}")
def delete_reservation(reserva_id: int, db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    reserva = db.query(Reserva).filter(Reserva.id == reserva_id).first()
    if not reserva:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada.")
    if current_user.role.nombre not in {"administrador", "empleado"} and reserva.usuario_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    db.delete(reserva)
    db.commit()
    return {"mensaje": "Reserva eliminada."}


@app.post("/api/contacto")
def contact_message(payload: ContactoCreate, db: Session = Depends(get_db)):
    mensaje = MensajeContacto(nombre=payload.nombre, correo=payload.correo.lower(), mensaje=payload.mensaje)
    db.add(mensaje)
    db.commit()
    return {"mensaje": "Mensaje enviado correctamente."}


@app.get("/api/contacto")
def list_contact_messages(db: Session = Depends(get_db), credentials: str = Depends(oauth2_scheme)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere un token JWT.")
    current_user = get_current_user(credentials, db)
    if current_user.role.nombre != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
    mensajes = db.query(MensajeContacto).order_by(MensajeContacto.id.desc()).all()
    return [{"id": m.id, "nombre": m.nombre, "correo": m.correo, "mensaje": m.mensaje, "creadoEn": m.creado_en.isoformat()} for m in mensajes]
