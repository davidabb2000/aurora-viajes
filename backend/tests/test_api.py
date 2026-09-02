import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Role, User

client = TestClient(app)


def test_register_and_login_user():
    suffix = uuid.uuid4().int % 1000000000
    payload = {
        "nombre": "Ana",
        "apellido": "Gomez",
        "tipoDocumento": "CC",
        "numeroDocumento": str(1000000000 + suffix),
        "direccion": "Calle 10 #20-30",
        "telefono": "3001234567",
        "correo": f"ana.{uuid.uuid4().hex[:8]}@example.com",
        "contrasena": "ClaveSegura1!",
    }

    response = client.post("/api/usuarios/registro", json=payload)
    assert response.status_code == 201, response.text

    login = client.post(
        "/api/auth/login",
        json={"correo": payload["correo"], "contrasena": payload["contrasena"]},
    )
    assert login.status_code == 200, login.text
    data = login.json()
    assert "token" in data
    assert data["usuario"]["correo"] == payload["correo"]


def test_protected_users_endpoint_requires_auth():
    response = client.get("/api/usuarios")
    assert response.status_code == 401


def test_products_crud_and_password_recovery_flow():
    suffix = uuid.uuid4().int % 1000000000
    registro = {
        "nombre": "Admin",
        "apellido": "Test",
        "tipoDocumento": "CC",
        "numeroDocumento": str(2000000000 + suffix),
        "direccion": "Cra 1 #2-3",
        "telefono": "3214567890",
        "correo": f"admin.{uuid.uuid4().hex[:8]}@example.com",
        "contrasena": "ClaveSegura1!",
    }
    response = client.post("/api/usuarios/registro", json=registro)
    assert response.status_code == 201, response.text

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.correo == registro["correo"]).first()
        admin_role = db.query(Role).filter(Role.nombre == "administrador").first()
        if user and admin_role:
            user.rol_id = admin_role.id
            db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/auth/login",
        json={"correo": registro["correo"], "contrasena": registro["contrasena"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["token"]

    crear = client.post(
        "/api/productos",
        json={"nombre": "Paquete Caribe", "descripcion": "Viaje de prueba", "precio": 1500000, "activo": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert crear.status_code == 200, crear.text
    producto_id = crear.json()["id"]

    listado = client.get("/api/productos")
    assert listado.status_code == 200, listado.text
    assert any(item["id"] == producto_id for item in listado.json())

    recuperar = client.post("/api/auth/recuperar", json={"correo": registro["correo"]})
    assert recuperar.status_code == 200, recuperar.text
    data = recuperar.json()
    assert "mensaje" in data
    assert "token" in data or "reset" in data["mensaje"].lower()

    nueva = client.post(
        "/api/auth/restablecer",
        json={"correo": registro["correo"], "token": data.get("token", "demo-token"), "nuevaContrasena": "NuevaClaveSegura2!"},
    )
    assert nueva.status_code == 200, nueva.text

    login_nuevo = client.post(
        "/api/auth/login",
        json={"correo": registro["correo"], "contrasena": "NuevaClaveSegura2!"},
    )
    assert login_nuevo.status_code == 200, login_nuevo.text


def test_admin_can_create_and_update_users_with_roles():
    login = client.post(
        "/api/auth/login",
        json={"correo": settings.ADMIN_EMAIL, "contrasena": settings.ADMIN_PASSWORD},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    suffix = uuid.uuid4().int % 1000000000
    nuevo_empleado = {
        "nombre": "Carlos",
        "apellido": "Ruiz",
        "tipoDocumento": "CC",
        "numeroDocumento": str(3000000000 + suffix),
        "direccion": "Av Siempre Viva 742",
        "telefono": "3009998877",
        "correo": f"empleado.{uuid.uuid4().hex[:8]}@example.com",
        "contrasena": "ClaveSegura1!",
        "rol": "empleado",
    }
    crear = client.post("/api/usuarios", json=nuevo_empleado, headers=headers)
    assert crear.status_code == 201, crear.text
    usuario_id = crear.json()["id"]

    detalle = client.get(f"/api/usuarios/{usuario_id}", headers=headers)
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["rol"] == "empleado"

    actualizar = client.put(
        f"/api/usuarios/{usuario_id}",
        json={"rol": "administrador", "telefono": "3001112233"},
        headers=headers,
    )
    assert actualizar.status_code == 200, actualizar.text

    detalle_actualizado = client.get(f"/api/usuarios/{usuario_id}", headers=headers)
    assert detalle_actualizado.json()["rol"] == "administrador"
    assert detalle_actualizado.json()["telefono"] == "3001112233"

    duplicado = client.post("/api/usuarios", json=nuevo_empleado, headers=headers)
    assert duplicado.status_code == 409, duplicado.text
