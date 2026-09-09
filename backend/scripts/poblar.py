"""Puebla la base con datos de ejemplo. Uso: python -m scripts.poblar"""

import asyncio

from sqlalchemy import select

from app.core.base_datos import Base, FabricaDeSesiones, motor
from app.core.seguridad import hashear_contrasena
from app.models.biblioteca import Autor, Categoria, Libro, Socio

CATEGORIAS = ['novela', 'memorias', 'tecnica', 'infantil', 'referencia']

AUTORES = [
    ('Gabriel García Márquez', 'Colombiana'),
    ('José Eustasio Rivera', 'Colombiana'),
    ('Héctor Abad Faciolince', 'Colombiana'),
    ('Thomas H. Cormen', 'Estadounidense'),
]

LIBROS = [
    ('Cien años de soledad', '9780307474728', 1967, 5, 3, 'Gabriel García Márquez', 'novela'),
    ('La vorágine', '9789583001123', 1924, 4, 4, 'José Eustasio Rivera', 'novela'),
    ('El olvido que seremos', '9789587582604', 2006, 3, 0, 'Héctor Abad Faciolince', 'memorias'),
    ('Introducción a los algoritmos', '9780262033848', 2009, 6, 2, 'Thomas H. Cormen', 'tecnica'),
]

SOCIOS = [
    ('1017234567', 'Laura Restrepo Gómez', 'laura.restrepo@example.com', True, 'socio', 'Socio2026*'),
    ('71654321', 'Andrés Villa Ochoa', 'andres.villa@example.com', True, 'bibliotecario', 'Biblio2026*'),
    ('1039876543', 'Sofía Marín Loaiza', 'sofia.marin@example.com', False, 'socio', 'Inactivo2026*'),
]


async def poblar() -> None:
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    async with FabricaDeSesiones() as sesion:
        if await sesion.scalar(select(Libro).limit(1)) is not None:
            print('La base ya tiene datos; no se hace nada.')
            return

        categorias = {n: Categoria(nombre=n) for n in CATEGORIAS}
        autores = {nombre: Autor(nombre=nombre, nacionalidad=nac) for nombre, nac in AUTORES}

        sesion.add_all([*categorias.values(), *autores.values()])
        await sesion.flush()  # asigna los id sin cerrar la transacción

        for titulo, isbn, anio, total, disponibles, autor, categoria in LIBROS:
            sesion.add(
                Libro(
                    titulo=titulo,
                    isbn=isbn,
                    anio_publicacion=anio,
                    ejemplares_totales=total,
                    ejemplares_disponibles=disponibles,
                    autor_id=autores[autor].id,
                    categoria_id=categorias[categoria].id,
                )
            )

        for documento, nombre, email, activo, rol, clave in SOCIOS:
            sesion.add(
                Socio(
                    documento=documento,
                    nombre=nombre,
                    email=email,
                    activo=activo,
                    rol=rol,
                    contrasena_hash=hashear_contrasena(clave),
                )
            )

        await sesion.commit()
        print('Base poblada: 5 categorías, 4 autores, 4 libros y 3 socios.')


if __name__ == '__main__':
    asyncio.run(poblar())

