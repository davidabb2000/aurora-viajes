import { useCallback, useEffect, useState } from "react";
import { solicitar } from "./api";

/**
 * Carga una ruta de la API y la mantiene al día.
 *
 * - `datos` conserva el último resultado bueno mientras llega el siguiente (al cambiar un filtro no parpadea).
 * - `cargando` se deduce de comparar la petición vigente con la última respuesta, sin escribir estado dentro del efecto.
 * - `recargar()` vuelve a pedirla (tras crear, editar o borrar algo).
 * - Con `ruta` vacía no pide nada.
 */
export function useCarga(ruta) {
  const [respuesta, setRespuesta] = useState({ ruta: null, version: -1, datos: null, error: "" });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!ruta) return undefined;
    let activo = true;
    solicitar(ruta)
      .then((datos) => activo && setRespuesta({ ruta, version, datos, error: "" }))
      .catch((error) => activo && setRespuesta((anterior) => ({ ruta, version, datos: anterior.datos, error: error.message })));
    return () => {
      activo = false;
    };
  }, [ruta, version]);

  const recargar = useCallback(() => setVersion((actual) => actual + 1), []);
  const vigente = respuesta.ruta === ruta && respuesta.version === version;
  return { datos: respuesta.datos, cargando: Boolean(ruta) && !vigente, error: vigente ? respuesta.error : "", recargar };
}
