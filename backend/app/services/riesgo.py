"""Servicio de predicción. Aísla scikit-learn del resto de la aplicación."""

from pathlib import Path

RUTA_MODELO = Path('modelos/riesgo_retraso.joblib')
VERSION_MODELO = 'riesgo_retraso-1.0'


class ModeloNoDisponible(RuntimeError):
    """El archivo del modelo no existe o no pudo cargarse."""


class ServicioDeRiesgo:
    def __init__(self, ruta: Path = RUTA_MODELO):
        if not ruta.exists():
            raise ModeloNoDisponible(f'No se encontró {ruta}. Ejecute: python -m scripts.entrenar_modelo')
        try:
            import joblib
        except ImportError as exc:
            raise ModeloNoDisponible('Falta joblib para cargar el modelo. Instale las dependencias del proyecto.') from exc
        self._joblib = joblib
        self._modelo = self._joblib.load(ruta)
        self.version = VERSION_MODELO

    def predecir(self, variables: dict) -> float:
        try:
            import pandas as pd
        except ImportError as exc:
            raise ModeloNoDisponible('Falta pandas para ejecutar la predicción. Instale las dependencias del proyecto.') from exc
        marco = pd.DataFrame([variables])
        return float(self._modelo.predict_proba(marco)[0, 1])

    @staticmethod
    def clasificar(probabilidad: float) -> tuple[str, str]:
        if probabilidad < 0.35:
            return ('bajo', 'Préstamo estándar: no requiere seguimiento especial.')
        if probabilidad < 0.65:
            return ('medio', 'Conviene enviar un recordatorio tres días antes del vencimiento.')
        return ('alto', 'Se sugiere acortar el plazo a 7 días y confirmar los datos de contacto.')