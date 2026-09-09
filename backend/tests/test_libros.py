import pytest

NUEVO = {
    'titulo': 'Libro Nuevo',
    'isbn': '9780000000010',
    'anio_publicacion': 2024,
    'ejemplares_totales': 3,
    'autor': 'Autora De Prueba',
    'categoria': 'novela',
}


def test_listar_catalogo(cliente):
    respuesta = cliente.get('/libros')
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 4
    assert respuesta.json()[0]['autor']['nombre'] == 'Autora De Prueba'


def test_filtrar_por_disponibilidad(cliente):
    respuesta = cliente.get('/libros?solo_disponibles=true')
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 3
    titulos = {libro['titulo'] for libro in respuesta.json()}
    assert 'Libro Agotado' not in titulos


def test_obtener_libro_inexistente(cliente):
    respuesta = cliente.get('/libros/999')
    assert respuesta.status_code == 404
    assert respuesta.json()['codigo'] == 'recurso_no_encontrado'


@pytest.mark.parametrize('libro_id', ['abc', '0', '-1'])
def test_identificador_invalido(cliente, libro_id):
    assert cliente.get(f'/libros/{libro_id}').status_code == 422


def test_crear_libro(cliente, cabecera_bibliotecario):
    respuesta = cliente.post('/libros', json=NUEVO, headers=cabecera_bibliotecario)
    assert respuesta.status_code == 201
    creado = respuesta.json()
    assert creado['ejemplares_disponibles'] == 3
    assert creado['categoria']['nombre'] == 'novela'


def test_crear_libro_con_isbn_repetido(cliente, cabecera_bibliotecario):
    cliente.post('/libros', json=NUEVO, headers=cabecera_bibliotecario)
    repetido = cliente.post('/libros', json=NUEVO, headers=cabecera_bibliotecario)
    assert repetido.status_code == 409


def test_crear_libro_con_autor_inexistente(cliente, cabecera_bibliotecario):
    respuesta = cliente.post('/libros', json={**NUEVO, 'autor_id': 999}, headers=cabecera_bibliotecario)
    assert respuesta.status_code == 404


def test_crear_libro_con_datos_invalidos(cliente, cabecera_bibliotecario):
    respuesta = cliente.post('/libros', json={**NUEVO, 'isbn': '123', 'anio_publicacion': 3000}, headers=cabecera_bibliotecario)
    assert respuesta.status_code == 422
    campos = {d['campo'] for d in respuesta.json()['detalles']}
    assert {'isbn', 'anio_publicacion'} <= campos


def test_actualizacion_parcial_no_borra_campos(cliente, cabecera_bibliotecario):
    respuesta = cliente.patch('/libros/1', json={'ejemplares_totales': 5}, headers=cabecera_bibliotecario)
    assert respuesta.status_code == 200
    assert respuesta.json()['titulo'] == 'Libro Disponible'
    assert respuesta.json()['ejemplares_disponibles'] == 5


def test_eliminar_libro(cliente, cabecera_bibliotecario):
    assert cliente.delete('/libros/1', headers=cabecera_bibliotecario).status_code == 204
    assert cliente.get('/libros/1').status_code == 404