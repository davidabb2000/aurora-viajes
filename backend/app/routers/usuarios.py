"""Registro público y gestión administrativa de usuarios."""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.limitador import limitar
from app.core.seguridad import hashear_contrasena
from app.dependencias import Administrador, SesionDep, UsuarioDeRuta
from app.errores import ConflictoDeNegocio, ErrorDeDominio
from app.models.dominio import PQR, Reserva, Role, User, Venta
from app.schemas.usuarios import EstadoUpdate, RegistroPublico, UserUpdate, UsuarioCreateAdmin
from app.services.catalogos import resolver_tipo_documento_id
from app.services.correos import enviar_correo_bienvenida
from app.services.serializadores import usuario_a_dict

router = APIRouter(tags=["usuarios"])

MENSAJE_DUPLICADO = "El correo o documento ya está registrado."


async def _rol(sesion, nombre: str) -> Role:
    rol = await sesion.scalar(select(Role).where(Role.nombre == nombre))
    if rol is None:
        raise ErrorDeDominio("Rol no válido.")
    return rol


async def _hay_otro_administrador(sesion, excluido_id: int) -> bool:
    """Debe quedar siempre al menos un administrador activo: sin él nadie podría gestionar la agencia."""
    cantidad = await sesion.scalar(
        select(func.count(User.id)).join(Role, Role.id == User.rol_id).where(
            Role.nombre == "administrador", User.activo.is_(True), User.id != excluido_id
        )
    )
    return bool(cantidad)


async def _tiene_historial(sesion, usuario_id: int) -> bool:
    for consulta in (
        select(func.count(Reserva.id)).where(Reserva.usuario_id == usuario_id),
        select(func.count(Venta.id)).where(or_(Venta.cliente_id == usuario_id, Venta.usuario_id == usuario_id)),
        select(func.count(PQR.id)).where(PQR.cliente_id == usuario_id),
    ):
        if await sesion.scalar(consulta):
            return True
    return False


@router.post("/api/usuarios/registro", status_code=status.HTTP_201_CREATED)
async def registrar_usuario(payload: RegistroPublico, peticion: Request, sesion: SesionDep, tareas: BackgroundTasks):
    await limitar(peticion, "registro", maximo=5, ventana_segundos=3600)
    existente = await sesion.scalar(select(User.id).where(or_(User.correo == payload.correo, User.numero_documento == payload.numeroDocumento)))
    if existente is not None:
        raise ConflictoDeNegocio(MENSAJE_DUPLICADO)
    rol = await _rol(sesion, "cliente")
    usuario = User(
        nombre=payload.nombre,
        apellido=payload.apellido,
        tipo_documento_id=await resolver_tipo_documento_id(sesion, payload.tipoDocumento),
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion,
        telefono=payload.telefono,
        correo=payload.correo,
        contrasena_hash=hashear_contrasena(payload.contrasena),
        rol_id=rol.id,
        activo=True,
        acepto_datos_en=datetime.now(timezone.utc),
    )
    sesion.add(usuario)
    try:
        await sesion.commit()
    except IntegrityError as exc:  # dos registros simultáneos con el mismo correo o documento
        await sesion.rollback()
        raise ConflictoDeNegocio(MENSAJE_DUPLICADO) from exc
    # El correo de bienvenida sale después de responder: el registro no espera al servidor SMTP.
    tareas.add_task(enviar_correo_bienvenida, usuario.correo, f"{usuario.nombre} {usuario.apellido}")
    return {"mensaje": "Cuenta creada correctamente."}


@router.get("/api/usuarios")
async def listar_usuarios(admin: Administrador, sesion: SesionDep):
    usuarios = await sesion.scalars(select(User).order_by(User.id.desc()))
    return [usuario_a_dict(usuario) for usuario in usuarios.unique()]


@router.post("/api/usuarios", status_code=status.HTTP_201_CREATED)
async def crear_usuario_admin(payload: UsuarioCreateAdmin, admin: Administrador, sesion: SesionDep):
    existente = await sesion.scalar(select(User.id).where(or_(User.correo == payload.correo, User.numero_documento == payload.numeroDocumento)))
    if existente is not None:
        raise ConflictoDeNegocio(MENSAJE_DUPLICADO)
    rol = await _rol(sesion, payload.rol)
    usuario = User(
        nombre=payload.nombre,
        apellido=payload.apellido,
        tipo_documento_id=await resolver_tipo_documento_id(sesion, payload.tipoDocumento),
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion,
        telefono=payload.telefono,
        correo=payload.correo,
        contrasena_hash=hashear_contrasena(payload.contrasena),
        rol_id=rol.id,
        activo=True,
        # La clave la eligió quien creó la cuenta: la persona debe cambiarla en su primer acceso.
        debe_cambiar_contrasena=True,
    )
    sesion.add(usuario)
    try:
        await sesion.commit()
    except IntegrityError as exc:
        await sesion.rollback()
        raise ConflictoDeNegocio(MENSAJE_DUPLICADO) from exc
    return {"id": usuario.id, "mensaje": "Usuario creado correctamente. Deberá cambiar su contraseña al entrar."}


@router.get("/api/usuarios/{usuario_id}")
async def obtener_usuario(usuario: UsuarioDeRuta, admin: Administrador):
    return usuario_a_dict(usuario)


@router.put("/api/usuarios/{usuario_id}")
async def actualizar_usuario(usuario: UsuarioDeRuta, payload: UserUpdate, admin: Administrador, sesion: SesionDep):
    if payload.correo is not None or payload.numeroDocumento is not None:
        correo = payload.correo if payload.correo is not None else usuario.correo
        documento = payload.numeroDocumento if payload.numeroDocumento is not None else usuario.numero_documento
        duplicado = await sesion.scalar(select(User.id).where(User.id != usuario.id, or_(User.correo == correo, User.numero_documento == documento)))
        if duplicado is not None:
            raise ConflictoDeNegocio(MENSAJE_DUPLICADO)
    if payload.rol is not None and payload.rol != usuario.role.nombre:
        if usuario.role.nombre == "administrador" and not await _hay_otro_administrador(sesion, usuario.id):
            raise ConflictoDeNegocio("Debe quedar al menos un administrador activo.")
        if usuario.id == admin.id:
            raise ConflictoDeNegocio("No puedes cambiar tu propio rol.")
        usuario.rol_id = (await _rol(sesion, payload.rol)).id
        usuario.sesion_version += 1  # el token viejo aún declara el rol anterior
    if payload.nombre is not None:
        usuario.nombre = payload.nombre
    if payload.apellido is not None:
        usuario.apellido = payload.apellido
    if payload.tipoDocumento is not None:
        usuario.tipo_documento_id = await resolver_tipo_documento_id(sesion, payload.tipoDocumento)
    if payload.numeroDocumento is not None:
        usuario.numero_documento = payload.numeroDocumento
    if payload.direccion is not None:
        usuario.direccion = payload.direccion
    if payload.telefono is not None:
        usuario.telefono = payload.telefono
    if payload.correo is not None:
        usuario.correo = payload.correo
    try:
        await sesion.commit()
    except IntegrityError as exc:
        await sesion.rollback()
        raise ConflictoDeNegocio(MENSAJE_DUPLICADO) from exc
    return {"mensaje": "Usuario actualizado."}


@router.patch("/api/usuarios/{usuario_id}/estado")
async def actualizar_estado_usuario(usuario: UsuarioDeRuta, payload: EstadoUpdate, admin: Administrador, sesion: SesionDep):
    if not payload.activo:
        if usuario.id == admin.id:
            raise ConflictoDeNegocio("No puedes desactivar tu propia cuenta.")
        if usuario.role.nombre == "administrador" and not await _hay_otro_administrador(sesion, usuario.id):
            raise ConflictoDeNegocio("Debe quedar al menos un administrador activo.")
    usuario.activo = payload.activo
    await sesion.commit()
    return {"mensaje": "Estado actualizado."}


@router.delete("/api/usuarios/{usuario_id}")
async def eliminar_usuario(usuario: UsuarioDeRuta, admin: Administrador, sesion: SesionDep):
    if usuario.id == admin.id:
        raise ConflictoDeNegocio("No puedes eliminar tu propia cuenta.")
    if usuario.role.nombre == "administrador" and not await _hay_otro_administrador(sesion, usuario.id):
        raise ConflictoDeNegocio("Debe quedar al menos un administrador activo.")
    if await _tiene_historial(sesion, usuario.id):
        raise ConflictoDeNegocio("Este usuario tiene reservas, ventas o PQR: desactívalo en lugar de eliminarlo para conservar el historial.")
    await sesion.delete(usuario)
    try:
        await sesion.commit()
    except IntegrityError as exc:
        await sesion.rollback()
        raise ConflictoDeNegocio("El usuario tiene datos asociados: desactívalo en lugar de eliminarlo.") from exc
    return {"mensaje": "Usuario eliminado."}
