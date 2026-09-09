import asyncio

from sqlalchemy import select

from app.models.biblioteca import Autor, Categoria, Libro


def test_riesgo_usa_el_modelo_sustituido(cliente, cabecera_bibliotecario, modelo_falso):
    respuesta = cliente.post(
        '/prestamos/riesgo',
        json={'libro_id': 1, 'socio_id': 1, 'dias_prestamo': 30},
        headers=cabecera_bibliotecario,
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo['version_modelo'] == 'modelo-de-prueba'
    assert cuerpo['nivel'] == 'alto'
    assert cuerpo['variables_usadas']['dias_prestamo'] == 30


def test_riesgo_con_menos_dias_baja_el_nivel(cliente, cabecera_bibliotecario, modelo_falso):
    respuesta = cliente.post(
        '/prestamos/riesgo',
        json={'libro_id': 1, 'socio_id': 1, 'dias_prestamo': 5},
        headers=cabecera_bibliotecario,
    )
    assert respuesta.json()['nivel'] == 'bajo'


def test_riesgo_con_libro_inexistente(cliente, cabecera_bibliotecario, modelo_falso):
    respuesta = cliente.post(
        '/prestamos/riesgo',
        json={'libro_id': 999, 'socio_id': 1},
        headers=cabecera_bibliotecario,
    )
    assert respuesta.status_code == 404


def test_recomendaciones_con_proveedor_simulado(cliente, cabecera_socio, proveedor_ia_falso):
    respuesta = cliente.post(
        '/recomendaciones',
        json={'intereses': 'Novelas colombianas contemporáneas y ensayo breve'},
        headers=cabecera_socio,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()['generada_por'] == 'modelo_externo'
    assert len(respuesta.json()['recomendaciones']) >= 1


def test_recomendaciones_locales_cambian_con_los_intereses(cliente, cabecera_socio, fabrica_sesiones, monkeypatch):
    from app.main import app

    # Fuerza el respaldo local sin depender de si el proveedor externo real está disponible.
    monkeypatch.setattr(app.state.servicio_recomendaciones, '_clave', None)

    async def insertar_libro_tecnico():
        async with fabrica_sesiones() as sesion:
            autor = await sesion.scalar(select(Autor).where(Autor.nombre == 'Autora De Prueba'))
            categoria = await sesion.scalar(select(Categoria).where(Categoria.nombre == 'tecnica'))
            sesion.add(
                Libro(
                    titulo='Guia de algoritmos practicos',
                    isbn='9789999999999',
                    anio_publicacion=2024,
                    ejemplares_totales=2,
                    ejemplares_disponibles=2,
                    autor_id=autor.id,
                    categoria_id=categoria.id,
                )
            )
            await sesion.commit()

    asyncio.run(insertar_libro_tecnico())

    respuesta = cliente.post(
        '/recomendaciones',
        json={'intereses': 'Quiero libros de tecnología y algoritmos para estudiar programación'},
        headers=cabecera_socio,
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo['generada_por'] == 'catalogo_local'
    assert cuerpo['recomendaciones'][0]['titulo'] == 'Guia de algoritmos practicos'


def test_recomendaciones_rechaza_entrada_corta(cliente, cabecera_socio):
    respuesta = cliente.post('/recomendaciones', json={'intereses': 'algo'}, headers=cabecera_socio)
    assert respuesta.status_code == 422


def test_recomendaciones_de_destinos_responde_con_catalogo_local(cliente, cabecera_socio, monkeypatch):
    from app.core.configuracion import configuracion

    monkeypatch.setattr(configuracion, 'proveedor_ia_api_key', None)
    respuesta = cliente.post(
        '/destinos/recomendaciones',
        json={'intereses': 'Quiero playa, descanso y cultura en familia'},
        headers=cabecera_socio,
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo['generada_por'] == 'catalogo_local'
    assert len(cuerpo['recomendaciones']) >= 1