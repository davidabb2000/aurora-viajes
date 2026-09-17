# Arquitectura Frontend - Aurora Viajes

## Descripción General
El frontend de Aurora Viajes está construido con React + Vite y sigue una arquitectura de componentes con separación clara de responsabilidades inspirada en patrones MVC/MVVM adaptados a React.

## Estructura de Carpetas

```
frontend/src/
├── components/              # Componentes reutilizables (UI/Presentación)
│   ├── Header.jsx          # Navegación principal
│   ├── Footer.jsx          # Pie de página
│   ├── Sidebar.jsx         # Menú lateral (admin/empleado)
│   ├── GoogleMap.jsx       # Mapa embebido
│   ├── Button.jsx          # Botón reutilizable
│   ├── Input.jsx           # Campo de entrada
│   ├── Modal.jsx           # Modal genérico
│   ├── Carousel.jsx        # Carrusel de destinos
│   ├── Select.jsx          # Dropdown
│   ├── RecoverPassword.jsx # Recuperación de contraseña
│   ├── RegisterModal.jsx   # Modal de registro
│   └── WhatsAppButton.jsx  # Botón WhatsApp flotante
│
├── pages/                   # Páginas (Vistas)
│   ├── Index.jsx           # Página de inicio
│   ├── Login.jsx           # Autenticación
│   ├── Panel.jsx           # Panel de usuario/admin
│   ├── Reservas.jsx        # Listar y crear reservas
│   ├── Recomendaciones.jsx # Recomendaciones IA
│   ├── PagoReserva.jsx     # Pago de reserva (Stripe)
│   ├── PagoExitoso.jsx     # Confirmación de pago
│   ├── Contacto.jsx        # Formulario de contacto
│   └── QuienesSomos.jsx    # Página informativa
│
├── layouts/                 # Layouts/Contenedores
│   ├── ClientLayout.jsx    # Layout con Header/Footer
│   └── AdminLayout.jsx     # Layout con Sidebar
│
├── context/                 # Estado global (React Context)
│   └── AuthContext.jsx     # Contexto de autenticación
│
├── utils/                   # Funciones utilitarias
│   ├── api.js              # Cliente HTTP (fetch wrapper)
│   └── validaciones.js     # Validadores de formularios
│
├── data/                    # Datos estáticos
│   └── destinos.js         # Lista de destinos
│
├── assets/                  # Recursos estáticos
│   └── images/             # Imágenes
│
├── App.jsx                  # Componente raíz (Router)
├── main.jsx                 # Punto de entrada
├── index.css               # Estilos Tailwind
└── vite.config.js          # Configuración Vite
```

## Patrones Implementados

### 1. **Components (Presentación)**
Componentes reutilizables que reciben datos vía props:

```jsx
// Button.jsx - Componente simple y reutilizable
function Button({ variant = "primario", children, onClick }) {
  return <button className={`btn btn-${variant}`}>{children}</button>;
}
```

**Tipos de Componentes:**
- **Componentes UI**: `Button`, `Input`, `Select`, `Modal`
- **Componentes de Negocio**: `RecoverPassword`, `RegisterModal`
- **Componentes de Layout**: `Header`, `Footer`, `Sidebar`

### 2. **Pages (Vistas)**
Páginas completas que representan rutas:

```jsx
// Login.jsx - Página de autenticación
function Login() {
  const { iniciarSesion } = useAuth();
  // lógica de formulario
  return (<form>...</form>);
}
```

### 3. **Layouts (Controladores de Layout)**
Contenedores que definen estructura visual:

```jsx
// ClientLayout.jsx
function ClientLayout({ children }) {
  return (
    <>
      <Header />
      <main>{children}</main>
      <Footer />
    </>
  );
}
```

### 4. **Context (Estado Global/Model)**
Gestión de estado compartido:

```jsx
// AuthContext.jsx
const AuthContext = createContext();

function AuthProvider({ children }) {
  const [sesion, setSesion] = useState(null);
  
  const iniciarSesion = async (correo, contrasena) => {
    // lógica de login
    setSesion(usuario);
  };
  
  return (
    <AuthContext.Provider value={{ sesion, iniciarSesion }}>
      {children}
    </AuthContext.Provider>
  );
}
```

### 5. **Utils (Servicios)**
Funciones reutilizables:

```javascript
// api.js - Cliente HTTP
export async function solicitar(ruta, opciones = {}) {
  const response = await fetch(`http://localhost:8000/api${ruta}`, opciones);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

// validaciones.js - Validadores
export function validarCorreo(correo) {
  if (!correo.includes("@")) return "Correo inválido";
  return "";
}
```

## Flujo de una Solicitud

1. **Usuario interactúa** en Page (ej: Login.jsx)
2. **Event handler** llama a función de utilidad (api.js)
3. **Solicitud HTTP** al backend
4. **Respuesta** actualiza Context (AuthContext)
5. **Componentes se re-renderizan** usando datos del Context
6. **UI se actualiza** con nuevos datos

## Patrones de Estado

### Context API (Estado Global)
```jsx
const { sesion } = useAuth(); // Acceso a datos globales
```

### useState (Estado Local)
```jsx
const [vista, setVista] = useState("reservas"); // Estado de componente
```

## Rutas (Routing)

En `App.jsx` usando React Router v6:

```jsx
<Routes>
  <Route path="/" element={<Index />} />
  <Route path="/login" element={<Login />} />
  <Route path="/panel" element={<Panel />} />
  // más rutas...
</Routes>
```

**Layouts condicionales:**
```jsx
if (esPanel && esAdmin && sesion) {
  return <AdminLayout><Panel /></AdminLayout>;
}
return <ClientLayout><Routes>...</Routes></ClientLayout>;
```

## Estilos

Se usa **Tailwind CSS** con configuración personalizada:
- Colores personalizados en `tailwind.config.js`
- Clases utilitarias para diseño responsive
- Componentes sin dependencias externas

## Validación de Formularios

```javascript
const validarCorreo = (correo) => {
  if (!correo) return "El correo es requerido";
  if (!correo.includes("@")) return "Correo inválido";
  return "";
};
```

## Integración con Backend

```javascript
// utils/api.js
export async function solicitar(ruta, opciones = {}) {
  const { headers = {} } = opciones;
  
  // Agregar token si existe
  if (sesion?.token) {
    headers.Authorization = `Bearer ${sesion.token}`;
  }
  
  return fetch(`http://localhost:8000/api${ruta}`, {
    ...opciones,
    headers,
  });
}
```

## Mejoras Futuras

1. **Redux o Zustand** para estado más complejo
2. **React Query** para cacheo de datos
3. **Error Boundary** para manejo de errores
4. **Lazy Loading** de componentes
5. **Testing** con Vitest y React Testing Library

## Conclusión

El frontend sigue una arquitectura **modular y escalable**:
- ✅ Componentes reutilizables
- ✅ Separación de Pages y Components
- ✅ Layouts bien definidos
- ✅ Context para estado global
- ✅ Validación centralizada
- ✅ API wrapper consistente
