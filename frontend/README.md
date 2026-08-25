# Aurora Viajes — Proyecto React + Vite

Ficha 3406211 · Ambiente 702 · Competencia React
Instructor: Jhan Hader Muñoz

## Avances incluidos

### Primer avance
- Proyecto React + Vite.
- Enrutamiento con React Router DOM (Inicio, ¿Quiénes Somos?, Contacto).
- Carrusel de 10 destinos (imagen, título, descripción).
- Componentes `Header`, `Footer`, `Carousel`.

### Segundo avance
- **Tailwind CSS** integrado mediante `@tailwindcss/vite`, con una paleta y
  tipografías propias definidas como tokens en `src/index.css` (`@theme`).
- Todos los componentes y páginas migrados a clases de Tailwind, responsivos.
- **Módulo de inicio de sesión** (`/login`): correo, contraseña, "Recordarme",
  enlace "¿Olvidaste tu contraseña?" y enlace "Crear una cuenta".
- **`RecoverPassword`**: componente independiente y reutilizable, con
  validación de correo y opción de regresar al login.
- **`RegisterModal`**: formulario de registro completo (nombre, apellido,
  tipo y número de documento, dirección, teléfono, correo, contraseña y
  confirmación), mostrado dentro de un Modal reutilizable, con cierre sin
  completar el registro.
- **Validaciones en tiempo real** (`src/utils/validaciones.js`): campos
  obligatorios, longitud mínima/máxima, RegEx, formato de correo, número de
  documento, teléfono, reglas de contraseña y coincidencia de confirmación.
- Componentes base reutilizables: `Input`, `Select`, `Button`, `Modal`.
- Uso de Hooks: `useState` para formularios y vistas, `useEffect` en `Modal`
  (bloqueo de scroll y cierre con Escape) y en `Carousel` (auto-reproducción).

## Estructura del proyecto
```
src/
├─ assets/images/       # 10 imágenes SVG del carrusel
├─ components/
│  ├─ Header.jsx / Footer.jsx / Carousel.jsx
│  ├─ Input.jsx / Select.jsx / Button.jsx / Modal.jsx
│  ├─ RecoverPassword.jsx
│  └─ RegisterModal.jsx
├─ pages/
│  ├─ Index.jsx / QuienesSomos.jsx / Contacto.jsx
│  └─ Login.jsx
├─ data/destinos.js      # Los 10 destinos del carrusel
├─ utils/validaciones.js # Validadores reutilizables (RegEx incluidas)
├─ App.jsx                # Enrutamiento (incluye /login)
├─ main.jsx                # Punto de entrada (BrowserRouter)
└─ index.css                # Import de Tailwind + tokens de diseño (@theme)
```

## Cómo ejecutarlo
```bash
npm install
npm run dev
```
Abre la URL que muestra la terminal (por defecto `http://localhost:5173`).
La ruta `/login` contiene el inicio de sesión, la recuperación de contraseña
y el botón que abre el modal de registro.

Para producción:
```bash
npm run build
npm run preview
```

### Tercer avance
- Integración con Node.js, Express, MySQL, bcrypt y JWT.
- Registro, login y recuperación conectados al backend.
- Reservas persistentes con destino, fechas, pasajeros, contacto, notas y estados.
- Paneles diferenciados para clientes, empleados y administradores.
- CRUD administrativo de usuarios y cambio de estado.

## Notas
- Las 10 imágenes del carrusel son ilustraciones SVG generadas para el
  ejercicio; reemplázalas en `src/assets/images` y actualiza las rutas en
  `src/data/destinos.js` si quieres usar fotografías reales.
