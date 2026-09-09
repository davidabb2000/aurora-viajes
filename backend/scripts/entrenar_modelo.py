"""Entrena el clasificador de riesgo de retraso. Uso: python -m scripts.entrenar_modelo"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RUTA_MODELO = Path('modelos/riesgo_retraso.joblib')
CATEGORIAS = ['novela', 'memorias', 'tecnica', 'infantil', 'referencia']
NUMERICAS = ['dias_prestamo', 'prestamos_previos', 'retrasos_previos', 'ejemplares_disponibles']
CATEGORICAS = ['categoria']


def generar_historico(n: int = 4000, semilla: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    dias = rng.integers(1, 31, n)
    previos = rng.integers(0, 25, n)
    retrasos = np.minimum(rng.poisson(1.2, n), previos)
    disponibles = rng.integers(0, 8, n)
    categoria = rng.choice(CATEGORIAS, n, p=[0.35, 0.15, 0.25, 0.15, 0.10])
    riesgo = (
        0.10 * dias + 0.55 * retrasos - 0.05 * previos
        + 0.8 * (categoria == 'tecnica') - 2.2 + rng.normal(0, 0.5, n)
    )
    probabilidad = 1 / (1 + np.exp(-riesgo))
    devuelto_tarde = rng.binomial(1, probabilidad)
    return pd.DataFrame({
        'dias_prestamo': dias, 'prestamos_previos': previos,
        'retrasos_previos': retrasos, 'ejemplares_disponibles': disponibles,
        'categoria': categoria, 'devuelto_tarde': devuelto_tarde,
    })


def construir_pipeline() -> Pipeline:
    preprocesamiento = ColumnTransformer(transformers=[
        ('numericas', StandardScaler(), NUMERICAS),
        ('categoricas', OneHotEncoder(categories=[CATEGORIAS], handle_unknown='ignore'), CATEGORICAS),
    ])
    return Pipeline(steps=[
        ('preprocesamiento', preprocesamiento),
        ('clasificador', RandomForestClassifier(
            n_estimators=200, max_depth=8, random_state=42, class_weight='balanced')),
    ])


def entrenar() -> None:
    datos = generar_historico()
    X = datos.drop(columns=['devuelto_tarde'])
    y = datos['devuelto_tarde']
    X_entreno, X_prueba, y_entreno, y_prueba = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
    modelo = construir_pipeline()
    modelo.fit(X_entreno, y_entreno)
    predicciones = modelo.predict(X_prueba)
    probabilidades = modelo.predict_proba(X_prueba)[:, 1]
    print(classification_report(y_prueba, predicciones, digits=3))
    print(f'ROC AUC: {roc_auc_score(y_prueba, probabilidades):.3f}')
    RUTA_MODELO.parent.mkdir(exist_ok=True)
    joblib.dump(modelo, RUTA_MODELO)
    print(f'Modelo guardado en {RUTA_MODELO}')


if __name__ == '__main__':
    entrenar()