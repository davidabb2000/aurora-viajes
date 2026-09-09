from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ConflictoDeNegocio, RecursoNoEncontrado
from app.models.biblioteca import Autor, Libro


async def listar(sesion: AsyncSession, limite: int = 10, desplazamiento: int = 0) -> list[Autor]:
    consulta = select(Autor).order_by(Autor.nombre).offset(desplazamiento).limit(limite)
    resultado = await sesion.scalars(consulta)
    return list(resultado)


async def obtener_o_fallar(sesion: AsyncSession, autor_id: int) -> Autor:
    autor = await sesion.get(Autor, autor_id)
    if autor is None:
        raise RecursoNoEncontrado('un autor', autor_id)
    return autor


async def contar_libros(sesion: AsyncSession, autor_id: int) -> int:
    return await sesion.scalar(
        select(func.count()).select_from(Libro).where(Libro.autor_id == autor_id)
    )


async def crear(sesion: AsyncSession, datos: dict) -> Autor:
    autor = Autor(**datos)
    sesion.add(autor)
    try:
        await sesion.commit()
    except IntegrityError:
        await sesion.rollback()
        raise ConflictoDeNegocio(f"Ya existe un autor llamado {datos['nombre']}.")
    await sesion.refresh(autor)
    return autor


async def actualizar(sesion: AsyncSession, autor: Autor, cambios: dict) -> Autor:
    for campo, valor in cambios.items():
        setattr(autor, campo, valor)
    try:
        await sesion.commit()
    except IntegrityError:
        await sesion.rollback()
        nombre = cambios.get('nombre', autor.nombre)
        raise ConflictoDeNegocio(f'Ya existe un autor llamado {nombre}.')
    await sesion.refresh(autor)
    return autor


async def eliminar(sesion: AsyncSession, autor: Autor) -> None:
    libros = await contar_libros(sesion, autor.id)
    if libros:
        raise ConflictoDeNegocio(f'El autor {autor.id} tiene {libros} libro(s) en el catálogo; no puede eliminarse.')
    await sesion.delete(autor)
    await sesion.commit()
