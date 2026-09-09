"""
Entrena el clasificador de riesgo de cancelación de viajes.
Uso: python -m scripts.entrenar_modelo
"""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RUTA_MODELO = Path('modelos/riesgo_cancelacion.joblib')

def generar_datos_ficticios(n=1000):
    """Genera datos históricos simulados para el entrenamiento."""
    np.random.seed(42)
    dias_antelacion = np.random.randint(1, 180, n)
    precio_paquete = np.random.randint(500, 5000, n)
    reservas_previas = np.random.randint(0, 10, n)
    cancelaciones_previas = np.random.randint(0, 5, n)
    
    # Lógica artificial: más cancelaciones previas y menos antelación = más riesgo
    riesgo = (cancelaciones_previas * 0.4) - (reservas_previas * 0.2) - (dias_antelacion * 0.01) + np.random.normal(0, 1, n)
    probabilidad = 1 / (1 + np.exp(-riesgo))
    cancelo_viaje = np.random.binomial(1, probabilidad)
    
    return pd.DataFrame({
        'dias_antelacion': dias_antelacion,
        'precio_paquete': precio_paquete,
        'reservas_previas': reservas_previas,
        'cancelaciones_previas': cancelaciones_previas,
        'cancelo_viaje': cancelo_viaje
    })

def entrenar():
    print("Generando datos históricos...")
    df = generar_datos_ficticios()
    X = df.drop(columns=['cancelo_viaje'])
    y = df['cancelo_viaje']

    print("Construyendo pipeline de Machine Learning...")
    preprocesamiento = ColumnTransformer(transformers=[
        ('num', StandardScaler(), ['dias_antelacion', 'precio_paquete', 'reservas_previas', 'cancelaciones_previas'])
    ])
    
    modelo = Pipeline(steps=[
        ('preprocesador', preprocesamiento),
        ('clasificador', RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', random_state=42))
    ])

    print("Entrenando el modelo...")
    modelo.fit(X, y)

    RUTA_MODELO.parent.mkdir(exist_ok=True)
    joblib.dump(modelo, RUTA_MODELO)
    print(f"¡Modelo guardado exitosamente en {RUTA_MODELO}!")

if __name__ == '__main__':
    entrenar()