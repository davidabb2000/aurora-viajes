def test_login_correcto_devuelve_token(cliente):
    respuesta = cliente.post('/auth/token', data={'username': '1000000002', 'password': 'Clave2026*'})
    assert respuesta.status_code == 200
    assert respuesta.json()['tipo'] == 'bearer'
    assert respuesta.json()['acceso']


def test_login_con_contrasena_incorrecta(cliente):
    respuesta = cliente.post('/auth/token', data={'username': '1000000002', 'password': 'incorrecta'})
    assert respuesta.status_code == 401
    assert respuesta.json()['codigo'] == 'no_autenticado'


def test_login_de_cuenta_inactiva(cliente):
    respuesta = cliente.post('/auth/token', data={'username': '1000000003', 'password': 'Clave2026*'})
    assert respuesta.status_code == 401


def test_endpoint_protegido_sin_token(cliente):
    respuesta = cliente.get('/socios')
    assert respuesta.status_code == 401
    assert respuesta.headers['www-authenticate'] == 'Bearer'


def test_socio_no_accede_a_recursos_de_bibliotecario(cliente, cabecera_socio):
    respuesta = cliente.get('/socios', headers=cabecera_socio)
    assert respuesta.status_code == 403
    assert respuesta.json()['codigo'] == 'permiso_denegado'


def test_token_invalido(cliente):
    respuesta = cliente.get('/auth/yo', headers={'Authorization': 'Bearer token-inventado'})
    assert respuesta.status_code == 401