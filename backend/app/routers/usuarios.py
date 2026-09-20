"""Registro público y gestión administrativa de usuarios."""
from fastapi import APIRouter, Request, status
from sqlalchemy import or_, select

from app.core.limitador import limitar
from app.core.seguridad import hashear_contrasena
from app.dependencias import Administrador, SesionDep, UsuarioDeRuta
from app.errores import ConflictoDeNegocio, ErrorDeDominio
from app.models.dominio import Role, User
from app.schemas.usuarios import EstadoUpdate, UserCreate, UserUpdate, UsuarioCreateAdmin
from app.services.catalogos import resolver_tipo_documento_id
from app.services.correos import enviar_correo_bienvenida
from app.services.serializadores import usuario_a_dict
from sqlalchemy.orm import selectinload

router = APIRouter(tags=["usuarios"])


@router.post("/api/usuarios/registro", status_code=status.HTTP_201_CREATED)
async def registrar_usuario(payload: UserCreate, peticion: Request, sesion: SesionDep):
    await limitar(peticion, "registro", maximo=5, ventana_segundos=3600)
    existente = await sesion.scalar(select(User).where(or_(User.correo == payload.correo.lower(), User.numero_documento == payload.numeroDocumento)))
    if existente is not None:
        raise ConflictoDeNegocio("El correo o documento ya está registrado.")
    rol = await sesion.scalar(select(Role).where(Role.nombre == "cliente"))
    if rol is None:
        rol = Role(nombre="cliente")
        sesion.add(rol)
        await sesion.flush()
    tipo_documento_id = await resolver_tipo_documento_id(sesion, payload.tipoDocumento)
    usuario = User(
        nombre=payload.nombre.strip(),
        apellido=payload.apellido.strip(),
        tipo_documento_id=tipo_documento_id,
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion.strip(),
        telefono=payload.telefono,
        correo=payload.correo.lower(),
        contrasena_hash=hashear_contrasena(payload.contrasena),
        rol_id=rol.id,
        activo=True,
    )
    sesion.add(usuario)
    await sesion.commit()
    await enviar_correo_bienvenida(usuario.correo, f"{usuario.nombre} {usuario.apellido}")
    return {"mensaje": "Cuenta creada correctamente."}


@router.get("/api/usuarios")
async def listar_usuarios(admin: Administrador, sesion: SesionDep):
    usuarios = await sesion.scalars(
        select(User).options(selectinload(User.role), selectinload(User.tipo_documento_catalogo)).order_by(User.id.desc())
    )
    return [usuario_a_dict(usuario) for usuario in usuarios]


@router.post("/api/usuarios", status_code=status.HTTP_201_CREATED)
async def crear_usuario_admin(payload: UsuarioCreateAdmin, admin: Administrador, sesion: SesionDep):
    existente = await sesion.scalar(select(User).where(or_(User.correo == payload.correo.lower(), User.numero_documento == payload.numeroDocumento)))
    if existente is not None:
        raise ConflictoDeNegocio("El correo o documento ya está registrado.")
    rol = await sesion.scalar(select(Role).where(Role.nombre == payload.rol))
    if rol is None:
        raise ErrorDeDominio("Rol no válido.")
    tipo_documento_id = await resolver_tipo_documento_id(sesion, payload.tipoDocumento)
    usuario = User(
        nombre=payload.nombre.strip(),
        apellido=payload.apellido.strip(),
        tipo_documento_id=tipo_documento_id,
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion.strip(),
        telefono=payload.telefono,
        correo=payload.correo.lower(),
        contrasena_hash=hashear_contrasena(payload.contrasena),
        rol_id=rol.id,
        activo=True,
    )
    sesion.add(usuario)
    await sesion.commit()
    return {"id": usuario.id, "mensaje": "Usuario creado correctamente."}


@router.get("/api/usuarios/{usuario_id}")
async def obtener_usuario(usuario: UsuarioDeRuta, admin: Administrador):
    return usuario_a_dict(usuario)


@router.put("/api/usuarios/{usuario_id}")
async def actualizar_usuario(usuario: UsuarioDeRuta, payload: UserUpdate, admin: Administrador, sesion: SesionDep):
    if payload.correo is not None or payload.numeroDocumento is not None:
        correo = payload.correo.lower() if payload.correo is not None else usuario.correo
        documento = payload.numeroDocumento if payload.numeroDocumento is not None else usuario.numero_documento
        duplicado = await sesion.scalar(select(User).where(User.id != usuario.id, or_(User.correo == correo, User.numero_documento == documento)))
        if duplicado is not None:
            raise ConflictoDeNegocio("El correo o documento ya está registrado.")
    if payload.nombre is not None:
        usuario.nombre = payload.nombre.strip()
    if payload.apellido is not None:
        usuario.apellido = payload.apellido.strip()
    if payload.tipoDocumento is not None:
        usuario.tipo_documento_id = await resolver_tipo_documento_id(sesion, payload.tipoDocumento)
    if payload.numeroDocumento is not None:
        usuario.numero_documento = payload.numeroDocumento
    if payload.direccion is not None:
        usuario.direccion = payload.direccion.strip()
    if payload.telefono is not None:
        usuario.telefono = payload.telefono
    if payload.correo is not None:
        usuario.correo = payload.correo.lower()
    if payload.rol is not None:
        rol = await sesion.scalar(select(Role).where(Role.nombre == payload.rol))
        if rol is None:
            raise ErrorDeDominio("Rol no válido.")
        usuario.rol_id = rol.id
    await sesion.commit()
    return {"mensaje": "Usuario actualizado."}


@router.patch("/api/usuarios/{usuario_id}/estado")
async def actualizar_estado_usuario(usuario: UsuarioDeRuta, payload: EstadoUpdate, admin: Administrador, sesion: SesionDep):
    usuario.activo = payload.activo
    await sesion.commit()
    return {"mensaje": "Estado actualizado."}


@router.delete("/api/usuarios/{usuario_id}")
async def eliminar_usuario(usuario: UsuarioDeRuta, admin: Administrador, sesion: SesionDep):
    await sesion.delete(usuario)
    await sesion.commit()
    return {"mensaje": "Usuario eliminado."}
