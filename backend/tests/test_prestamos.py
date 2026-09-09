def _prestar(cliente, cabecera, libro_id=1, socio_id=1, dias=15):
    return cliente.post(
        '/prestamos',
        json={'libro_id': libro_id, 'socio_id': socio_id, 'dias_prestamo': dias},
        headers=cabecera,
    )


def test_prestamo_descuenta_un_ejemplar(cliente, cabecera_bibliotecario):
    respuesta = _prestar(cliente, cabecera_bibliotecario)
    assert respuesta.status_code == 201
    assert respuesta.json()['estado'] == 'activo'
    assert cliente.get('/libros/1').json()['ejemplares_disponibles'] == 1


def test_prestamo_sin_ejemplares(cliente, cabecera_bibliotecario):
    respuesta = _prestar(cliente, cabecera_bibliotecario, libro_id=4)
    assert respuesta.status_code == 409
    assert respuesta.json()['codigo'] == 'sin_ejemplares_disponibles'


def test_prestamo_a_socio_inactivo(cliente, cabecera_bibliotecario):
    respuesta = _prestar(cliente, cabecera_bibliotecario, socio_id=3)
    assert respuesta.status_code == 409
    assert respuesta.json()['codigo'] == 'socio_inactivo'


def test_limite_de_prestamos_activos(cliente, cabecera_bibliotecario):
    for libro_id in (1, 2, 3):
        assert _prestar(cliente, cabecera_bibliotecario, libro_id=libro_id).status_code == 201
    cuarto = _prestar(cliente, cabecera_bibliotecario, libro_id=2)
    assert cuarto.status_code == 409
    assert cuarto.json()['codigo'] == 'limite_de_prestamos_superado'


def test_no_se_repite_el_mismo_prestamo_el_mismo_dia(cliente, cabecera_bibliotecario):
    assert _prestar(cliente, cabecera_bibliotecario).status_code == 201
    repetido = _prestar(cliente, cabecera_bibliotecario)
    assert repetido.status_code == 409
    assert 'ya tiene registrado hoy' in repetido.json()['mensaje']


def test_dias_fuera_de_rango(cliente, cabecera_bibliotecario):
    assert _prestar(cliente, cabecera_bibliotecario, dias=90).status_code == 422
    assert _prestar(cliente, cabecera_bibliotecario, dias=0).status_code == 422


def test_devolucion_repone_el_ejemplar(cliente, cabecera_bibliotecario):
    _prestar(cliente, cabecera_bibliotecario)
    respuesta = cliente.post('/prestamos/1/devolucion', headers=cabecera_bibliotecario)
    assert respuesta.status_code == 200
    assert respuesta.json()['estado'] == 'devuelto'
    assert cliente.get('/libros/1').json()['ejemplares_disponibles'] == 2


def test_devolucion_repetida(cliente, cabecera_bibliotecario):
    _prestar(cliente, cabecera_bibliotecario)
    cliente.post('/prestamos/1/devolucion', headers=cabecera_bibliotecario)
    segunda = cliente.post('/prestamos/1/devolucion', headers=cabecera_bibliotecario)
    assert segunda.status_code == 409
    assert segunda.json()['codigo'] == 'prestamo_ya_devuelto'


def test_socio_solo_ve_sus_prestamos(cliente, cabecera_bibliotecario, cabecera_socio):
    _prestar(cliente, cabecera_bibliotecario, socio_id=1)
    del_socio = cliente.get('/prestamos', headers=cabecera_socio).json()
    del_bibliotecario = cliente.get('/prestamos', headers=cabecera_bibliotecario).json()
    assert all(p['socio_id'] == 1 for p in del_socio)
    assert len(del_bibliotecario) >= len(del_socio)


def test_no_se_elimina_un_libro_prestado(cliente, cabecera_bibliotecario):
    _prestar(cliente, cabecera_bibliotecario)
    respuesta = cliente.delete('/libros/1', headers=cabecera_bibliotecario)
    assert respuesta.status_code == 409