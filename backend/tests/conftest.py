"""Fixtures compartidas por toda la batería de pruebas."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.base_datos import Base, obtener_sesion
from app.core.seguridad import hashear_contrasena
from app.dependencias import obtener_servicio_riesgo
from app.main import app
from app.models.biblioteca import Autor, Categoria, Libro, Socio
from app.services.recomendaciones import ServicioDeRecomendaciones


@pytest.fixture
def motor_prueba():
    motor = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    yield motor


@pytest.fixture
def fabrica_sesiones(motor_prueba):
    return async_sessionmaker(bind=motor_prueba, expire_on_commit=False)


@pytest.fixture
def cliente(motor_prueba, fabrica_sesiones):
    async def sesion_de_prueba():
        async with fabrica_sesiones() as sesion:
            yield sesion

    app.dependency_overrides[obtener_sesion] = sesion_de_prueba
    prueba = TestClient(app, raise_server_exceptions=False)

    async def preparar():
        async with motor_prueba.begin() as conexion:
            await conexion.run_sync(Base.metadata.create_all)

        async with fabrica_sesiones() as sesion:
            categoria = Categoria(nombre='novela')
            tecnica = Categoria(nombre='tecnica')
            autor = Autor(nombre='Autora De Prueba', nacionalidad='Colombiana')
            sesion.add_all([categoria, tecnica, autor])
            await sesion.flush()
            sesion.add_all([
                Libro(
                    titulo='Libro Disponible',
                    isbn='9780000000001',
                    anio_publicacion=2020,
                    ejemplares_totales=2,
                    ejemplares_disponibles=2,
                    autor_id=autor.id,
                    categoria_id=categoria.id,
                ),
                Libro(
                    titulo='Libro Tercero',
                    isbn='9780000000003',
                    anio_publicacion=2015,
                    ejemplares_totales=4,
                    ejemplares_disponibles=4,
                    autor_id=autor.id,
                    categoria_id=categoria.id,
                ),
                Libro(
                    titulo='Libro Cuarto',
                    isbn='9780000000004',
                    anio_publicacion=2012,
                    ejemplares_totales=4,
                    ejemplares_disponibles=4,
                    autor_id=autor.id,
                    categoria_id=categoria.id,
                ),
                Libro(
                    titulo='Libro Agotado',
                    isbn='9780000000009',
                    anio_publicacion=2018,
                    ejemplares_totales=1,
                    ejemplares_disponibles=0,
                    autor_id=autor.id,
                    categoria_id=tecnica.id,
                ),
                Socio(
                    documento='1000000001',
                    nombre='Socia De Prueba',
                    email='socia@example.com',
                    activo=True,
                    rol='socio',
                    contrasena_hash=hashear_contrasena('Clave2026*'),
                ),
                Socio(
                    documento='1000000002',
                    nombre='Bibliotecario De Prueba',
                    email='biblio@example.com',
                    activo=True,
                    rol='bibliotecario',
                    contrasena_hash=hashear_contrasena('Clave2026*'),
                ),
                Socio(
                    documento='1000000003',
                    nombre='Socia Inactiva',
                    email='inactiva@example.com',
                    activo=False,
                    rol='socio',
                    contrasena_hash=hashear_contrasena('Clave2026*'),
                ),
            ])
            await sesion.commit()

    asyncio.run(preparar())
    with prueba:
        yield prueba
    app.dependency_overrides.clear()


def _token(cliente, documento: str) -> str:
    respuesta = cliente.post('/auth/token', data={'username': documento, 'password': 'Clave2026*'})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()['acceso']


@pytest.fixture
def cabecera_socio(cliente):
    return {'Authorization': f"Bearer {_token(cliente, '1000000001')}"}


@pytest.fixture
def cabecera_bibliotecario(cliente):
    return {'Authorization': f"Bearer {_token(cliente, '1000000002')}"}


class ModeloFalso:
    version = 'modelo-de-prueba'

    def predecir(self, variables: dict) -> float:
        return min(0.05 + variables['dias_prestamo'] * 0.03, 0.99)

    @staticmethod
    def clasificar(probabilidad: float) -> tuple[str, str]:
        if probabilidad < 0.35:
            return 'bajo', 'Préstamo estándar.'
        if probabilidad < 0.65:
            return 'medio', 'Enviar recordatorio.'
        return 'alto', 'Acortar el plazo.'


@pytest.fixture
def modelo_falso():
    app.state.servicio_riesgo = ModeloFalso()
    app.dependency_overrides[obtener_servicio_riesgo] = lambda: app.state.servicio_riesgo
    yield
    app.dependency_overrides.pop(obtener_servicio_riesgo, None)
    app.state.servicio_riesgo = None


@pytest.fixture
def proveedor_ia_falso(monkeypatch):
    def responder(peticion: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(peticion.content)
        catalogo = json.loads(cuerpo['messages'][1]['content'].split('Catálogo disponible:')[1])
        recomendaciones = [
            {
                'libro_id': libro['libro_id'],
                'titulo': libro['titulo'],
                'motivo': 'Coincide con los intereses indicados.',
            }
            for libro in catalogo[:3]
        ]
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(recomendaciones)}}]})

    from app.core.configuracion import configuracion

    monkeypatch.setattr(configuracion, 'proveedor_ia_api_key', 'clave-de-prueba')
    cliente_http = httpx.AsyncClient(transport=httpx.MockTransport(responder))
    app.state.cliente_http = cliente_http
    app.state.servicio_recomendaciones = ServicioDeRecomendaciones(cliente_http)
    yield
    asyncio.run(cliente_http.aclose())
    app.state.cliente_http = None
    app.state.servicio_recomendaciones = None