from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ConflictoDeNegocio, RecursoNoEncontrado
from app.models.biblioteca import Autor, Categoria, Libro, Prestamo


def normalizar_texto(valor: str) -> str:
    return ' '.join(str(valor).split())


async def _resolver_autor(sesion: AsyncSession, nombre: str) -> Autor:
    nombre = normalizar_texto(nombre)
    autor = await sesion.scalar(select(Autor).where(Autor.nombre.ilike(f'%{nombre}%')).limit(1))
    if autor is not None:
        return autor
    autor = Autor(nombre=nombre, nacionalidad='Desconocida')
    sesion.add(autor)
    await sesion.flush()
    return autor


async def _resolver_categoria(sesion: AsyncSession, nombre: str) -> Categoria:
    nombre = normalizar_texto(nombre).lower()
    categoria = await sesion.scalar(select(Categoria).where(Categoria.nombre.ilike(nombre)).limit(1))
    if categoria is not None:
        return categoria
    categoria = Categoria(nombre=nombre)
    sesion.add(categoria)
    await sesion.flush()
    return categoria


async def listar(
    sesion: AsyncSession,
    categoria: str | None = None,
    anio_min: int | None = None,
    buscar: str | None = None,
    solo_disponibles: bool = False,
    limite: int = 10,
    desplazamiento: int = 0,
) -> list[Libro]:
    consulta = select(Libro)
    if categoria is not None:
        consulta = consulta.join(Libro.categoria).where(Categoria.nombre == categoria)
    if anio_min is not None:
        consulta = consulta.where(Libro.anio_publicacion >= anio_min)
    if buscar is not None:
        consulta = consulta.where(Libro.titulo.ilike(f'%{buscar}%'))
    if solo_disponibles:
        consulta = consulta.where(Libro.ejemplares_disponibles > 0)
    consulta = consulta.order_by(Libro.titulo).offset(desplazamiento).limit(limite)
    resultado = await sesion.scalars(consulta)
    return list(resultado.unique())


async def obtener_o_fallar(sesion: AsyncSession, libro_id: int) -> Libro:
    libro = await sesion.get(Libro, libro_id)
    if libro is None:
        raise RecursoNoEncontrado('un libro', libro_id)
    return libro


async def _validar_relaciones(sesion: AsyncSession, autor_id: int, categoria_id: int) -> None:
    if await sesion.get(Autor, autor_id) is None:
        raise RecursoNoEncontrado('un autor', autor_id)
    if await sesion.get(Categoria, categoria_id) is None:
        raise RecursoNoEncontrado('una categoría', categoria_id)


async def crear(sesion: AsyncSession, datos: dict) -> Libro:
    autor_id = datos.get('autor_id')
    categoria_id = datos.get('categoria_id')

    if autor_id is None:
        autor = await _resolver_autor(sesion, datos['autor'])
        autor_id = autor.id
    elif await sesion.get(Autor, autor_id) is None:
        raise RecursoNoEncontrado('un autor', autor_id)

    if categoria_id is None:
        categoria = await _resolver_categoria(sesion, datos['categoria'])
        categoria_id = categoria.id
    elif await sesion.get(Categoria, categoria_id) is None:
        raise RecursoNoEncontrado('una categoría', categoria_id)

    datos = {**datos, 'autor_id': autor_id, 'categoria_id': categoria_id}
    datos.pop('autor', None)
    datos.pop('categoria', None)
    libro = Libro(**datos, ejemplares_disponibles=datos['ejemplares_totales'])
    sesion.add(libro)
    try:
        await sesion.commit()
    except IntegrityError:
        await sesion.rollback()
        raise ConflictoDeNegocio(f"Ya existe un libro registrado con el ISBN {datos['isbn']}.")
    await sesion.refresh(libro, attribute_names=['autor', 'categoria'])
    return libro


async def actualizar(sesion: AsyncSession, libro: Libro, cambios: dict) -> Libro:
    if 'autor' in cambios:
        autor = await _resolver_autor(sesion, cambios['autor'])
        cambios = {**cambios, 'autor_id': autor.id}
        cambios.pop('autor', None)
    if 'categoria' in cambios:
        categoria = await _resolver_categoria(sesion, cambios['categoria'])
        cambios = {**cambios, 'categoria_id': categoria.id}
        cambios.pop('categoria', None)
    if 'autor_id' in cambios or 'categoria_id' in cambios:
        await _validar_relaciones(
            sesion,
            cambios.get('autor_id', libro.autor_id),
            cambios.get('categoria_id', libro.categoria_id),
        )
    if 'ejemplares_totales' in cambios:
        prestados = libro.ejemplares_totales - libro.ejemplares_disponibles
        libro.ejemplares_disponibles = max(cambios['ejemplares_totales'] - prestados, 0)
    for campo, valor in cambios.items():
        setattr(libro, campo, valor)
    await sesion.commit()
    await sesion.refresh(libro, attribute_names=['autor', 'categoria'])
    return libro


async def eliminar(sesion: AsyncSession, libro: Libro) -> None:
    activos = await sesion.scalar(
        select(func.count()).select_from(Prestamo)
        .where(Prestamo.libro_id == libro.id, Prestamo.fecha_devolucion_real.is_(None))
    )
    if activos:
        raise ConflictoDeNegocio(f'El libro {libro.id} tiene {activos} préstamo(s) activo(s); no puede eliminarse.')
    await sesion.delete(libro)
    await sesion.commit()
