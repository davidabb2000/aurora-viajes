from pathlib import Path

RUTA_MODELO = Path('modelos/riesgo_cancelacion.joblib')

class ModeloNoDisponible(RuntimeError):
    pass

class ServicioDeRiesgo:
    def __init__(self):
        if not RUTA_MODELO.exists():
            self._modelo = None
        else:
            import joblib
            self._modelo = joblib.load(RUTA_MODELO)
            
        self.version = 'riesgo_cancelacion-1.0'

    def predecir(self, variables: dict) -> float:
        if not self._modelo:
            return 0.05 # Riesgo bajo por defecto si no hay modelo entrenado
            
        import pandas as pd
        marco = pd.DataFrame([variables])
        # Asumimos que la columna 1 es la probabilidad de cancelación
        return float(self._modelo.predict_proba(marco)[0, 1])

    @staticmethod
    def clasificar(probabilidad: float) -> tuple[str, str]:
        if probabilidad < 0.35:
            return ('bajo', 'Cliente confiable. Proceder con política estándar.')
        if probabilidad < 0.65:
            return ('medio', 'Riesgo moderado. Enviar recordatorios de pago tempranos.')
        return ('alto', 'Alto riesgo de cancelación. Exigir abono no reembolsable del 50%.')