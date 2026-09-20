"""Formulario de contacto."""
from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.limitador import limitar
from app.dependencias import Administrador, SesionDep
from app.models.dominio import MensajeContacto
from app.schemas.contacto import ContactoCreate

router = APIRouter(tags=["contacto"])


@router.post("/api/contacto")
async def crear_contacto(payload: ContactoCreate, peticion: Request, sesion: SesionDep):
    await limitar(peticion, "contacto", maximo=5, ventana_segundos=3600)
    mensaje = MensajeContacto(nombre=payload.nombre, correo=payload.correo.lower(), mensaje=payload.mensaje)
    sesion.add(mensaje)
    await sesion.commit()
    return {"mensaje": "Mensaje enviado correctamente."}


@router.get("/api/contacto")
async def listar_contactos(admin: Administrador, sesion: SesionDep):
    mensajes = await sesion.scalars(select(MensajeContacto).order_by(MensajeContacto.id.desc()))
    return [{"id": mensaje.id, "nombre": mensaje.nombre, "correo": mensaje.correo, "mensaje": mensaje.mensaje, "creadoEn": mensaje.creado_en.isoformat()} for mensaje in mensajes]
