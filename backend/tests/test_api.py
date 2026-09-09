def test_salud_y_metadatos(cliente):
    respuesta = cliente.get('/salud')
    assert respuesta.status_code == 200
    assert respuesta.json() == {'estado': 'ok'}
    assert respuesta.headers['X-Content-Type-Options'] == 'nosniff'
    assert 'X-Peticion-Id' in respuesta.headers


def test_listado_filtrado_y_ruta_fija(cliente):
    assert cliente.get('/libros?categoria=novela&solo_disponibles=true').status_code == 200
    assert len(cliente.get('/libros/disponibles').json()) == 3


def test_errores_normalizados(cliente):
    encontrado = cliente.get('/libros/99')
    assert encontrado.status_code == 404
    assert encontrado.json()['codigo'] == 'recurso_no_encontrado'
    invalido = cliente.get('/libros/abc')
    assert invalido.status_code == 422
    assert invalido.json()['codigo'] == 'datos_invalidos'


def test_crud_y_autorizacion(cliente, cabecera_bibliotecario):
    payload = {
        'titulo': 'Delirio',
        'isbn': '9788483462744',
        'anio_publicacion': 2004,
        'autor': 'Laura Restrepo',
        'categoria': 'novela',
        'ejemplares_totales': 4,
    }
    creado = cliente.post('/libros', json=payload, headers=cabecera_bibliotecario)
    assert creado.status_code == 201
    duplicado = cliente.post('/libros', json=payload, headers=cabecera_bibliotecario)
    assert duplicado.status_code == 409
    assert cliente.delete(f"/libros/{creado.json()['id']}", headers=cabecera_bibliotecario).status_code == 204