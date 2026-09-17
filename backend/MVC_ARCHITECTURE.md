# Arquitectura MVC de Aurora Viajes

## Descripción General
El proyecto Aurora Viajes Backend sigue un patrón de arquitectura limpia con separación de responsabilidades inspirado en MVC (Model-View-Controller).

## Estructura de Carpetas

```
backend/app/
├── core/                    # Configuración y servicios centrales
│   ├── base_datos.py       # Conexión a BD y sesiones
│   ├── configuracion.py    # Variables de entorno y config
│   └── seguridad.py        # Autenticación y encriptación
│
├── models/                  # MODELS - Definición de entidades
│   └── biblioteca.py       # Modelos SQLAlchemy (User, Reserva, etc.)
│
├── schemas/                 # VIEWS - Serialización de datos
│   ├── diagnostico.py      # Schemas de respuesta para diagnóstico
│   └── error.py            # Schemas de errores
│
├── crud/                    # CONTROLLERS - Lógica CRUD por entidad
│   └── [Vacío - lógica ahora en main.py]
│
├── routers/                 # Endpoints/Rutas
│   ├── recomendaciones.py  # Rutas de recomendaciones
│   └── sistema.py          # Rutas de diagnóstico del sistema
│
├── services/                # LÓGICA DE NEGOCIO - Servicios
│   ├── recomendaciones.py  # Servicio de recomendaciones IA
│   ├── correos.py          # Servicio de envío de emails
│   └── riesgo.py           # Servicio de predicción de riesgo
│
├── main.py                  # Aplicación FastAPI principal
├── dependencias.py          # Inyección de dependencias
├── errores.py              # Definición de excepciones personalizadas
└── middlewares.py          # Middlewares de FastAPI
```

## Patrones Implementados

### 1. **Models (Modelos)**
Ubicación: `app/models/biblioteca.py`

Define la estructura de datos usando SQLAlchemy ORM:
- User (usuario)
- Reserva
- Destino, Pais
- Role, Permiso
- MensajeContacto
- EstadoReserva, EstadoPago, MetodoPago

```python
class User(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    # ... atributos ...
```

### 2. **Views (Schemas/Serialización)**
Ubicación: `app/schemas/`

Define los formatos de entrada/salida usando Pydantic:
- `UserCreate`, `UserLogin`, `UserUpdate`
- `ReservaCreate`, `ReservaUpdate`
- `ContactoCreate`
- Validadores personalizados

### 3. **Controllers (Rutas/Endpoints)**
Ubicación: `app/main.py` y `app/routers/`

Definen los endpoints y lógica de request/response:
- POST `/api/auth/login` - Autenticación
- GET `/api/reservas` - Listar reservas
- POST `/api/reservas` - Crear reserva
- PUT `/api/reservas/{id}` - Actualizar reserva
- DELETE `/api/reservas/{id}` - Eliminar reserva
- GET `/api/usuarios` - Listar usuarios
- POST `/api/usuarios` - Crear usuario (solo admin)
- Etc.

### 4. **Services (Lógica de Negocio)**
Ubicación: `app/services/`

Encapsula la lógica compleja:
- `correos.py` - Envío de correos
- `recomendaciones.py` - Integración con IA
- `riesgo.py` - Modelo de predicción

### 5. **Middleware & Seguridad**
Ubicación: `app/middlewares.py`, `app/core/seguridad.py`

- Validación de JWT
- Manejo de CORS
- Cabeceras de seguridad
- Hash de contraseñas

### 6. **Manejo de Errores**
Ubicación: `app/errores.py`

Excepciones personalizadas:
- `ErrorDeDominio` - Errores de lógica de negocio
- `NoAutenticado` - Falta de autenticación
- `PermisoDenegado` - Falta de permisos
- `RecursoNoEncontrado` - 404
- `ConflictoDeNegocio` - Conflictos (409)

## Flujo Típico de una Solicitud

1. **Request llega a endpoint** (Router/Controller en main.py)
2. **Validación de Schema** (Pydantic valida entrada)
3. **Validación de Autenticación** (JWT verificado en dependencias)
4. **Lógica de Negocio** (Se ejecuta en el endpoint)
5. **Acceso a Base de Datos** (Mediante SQLAlchemy ORM)
6. **Response con Schema** (Serialización de salida)

## Recomendaciones de Mejora

Para una mejor separación MVC, considerar:

1. **Extractar controladores CRUD** a archivos separados en `app/crud/`
   ```
   app/crud/
   ├── usuarios.py
   ├── reservas.py
   ├── destinos.py
   └── mensajes.py
   ```

2. **Usar Repositories** para acceso a datos
   ```python
   class UsuarioRepository:
       async def crear(self, datos)
       async def obtener(self, id)
       async def actualizar(self, id, datos)
   ```

3. **DTOs para respuestas** más claros
   ```python
   class UsuarioResponse(BaseModel):
       id: int
       nombre: str
       # solo campos públicos
   ```

4. **Use cases o Application Services** para lógica compleja
   ```python
   class CrearReservaUseCase:
       async def ejecutar(self, datos)
   ```

## Conclusión

La arquitectura actual **sigue principios de MVC** de forma funcional:
- **Models**: Definidos claramente en `models/`
- **Views**: Implementados como Schemas en `schemas/`
- **Controllers**: Endpoints en `main.py` y `routers/`
- **Services**: Lógica de negocio en `services/`
- **Inyección de dependencias**: Limpia y bien organizada

El proyecto está bien estructurado y es mantenible. Las mejoras sugeridas son opcionales pero recomendadas para proyectos más grandes.
