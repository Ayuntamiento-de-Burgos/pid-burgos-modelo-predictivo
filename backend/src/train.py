"""
train.py — CU#48 Burgos
Entrenamiento del modelo Prophet por zona del pliego.
Aplica ventana de entrenamiento con límite de 2 años y
inicio desde cuando hay todas las variables exógenas disponibles.
"""

import logging

import numpy as np
import pandas as pd
from prophet import Prophet

from config import PROPHET_PARAMS, REGRESSORS, ZONAS_PLIEGO, get_train_ini

LOGGER = logging.getLogger(__name__)


def mape_diario(df_real: pd.DataFrame, df_pred: pd.DataFrame) -> float:
    """
    MAPE a nivel diario (suma de horas del día).
    Excluye días con y_real=0 o con más del 50% de horas con sensor_down.
    """
    merged = df_pred[["ds", "yhat"]].merge(
        df_real[["ds", "y"]], on="ds", how="inner")
    merged["fecha"] = merged["ds"].dt.date

    diario = merged.groupby("fecha").agg(
        y_real=("y", "sum"),
        y_pred=("yhat", "sum"),
    ).reset_index()

    diario = diario[diario["y_real"] > 0]
    if len(diario) == 0:
        return np.nan

    return (np.abs(diario["y_real"] - diario["y_pred"]) /
            diario["y_real"]).mean() * 100


def mape_periodo(df_real: pd.DataFrame, df_pred: pd.DataFrame) -> float:
    """
    MAPE del período completo (suma total predicha vs suma total real).
    Más estable que el MAPE diario medio cuando hay días con errores extremos.
    """
    merged = df_pred[["ds", "yhat"]].merge(
        df_real[["ds", "y"]], on="ds", how="inner")
    merged["fecha"] = merged["ds"].dt.date

    diario = merged.groupby("fecha").agg(
        y_real=("y", "sum"),
        y_pred=("yhat", "sum"),
    ).reset_index()

    diario = diario[diario["y_real"] > 0]
    if len(diario) == 0 or diario["y_real"].sum() == 0:
        return np.nan

    return (abs(diario["y_real"].sum() - diario["y_pred"].sum()) /
            diario["y_real"].sum()) * 100


def train_zona(zona_num: int, prophet_df: pd.DataFrame,
               fecha_prediccion: pd.Timestamp) -> tuple:
    """
    Entrena Prophet para una zona aplicando la ventana de entrenamiento.
    - Inicio: max(TRAIN_INI_GLOBAL, ventana_2_años, inicio_sensor)
    - Fin: día anterior a fecha_prediccion
    Devuelve (modelo, train_df).
    """
    inicio_sensor  = prophet_df["ds"].min()
    train_ini      = get_train_ini(fecha_prediccion, inicio_sensor)
    train_fin      = fecha_prediccion - pd.Timedelta(days=1)

    train = prophet_df[
        (prophet_df["ds"] >= train_ini) &
        (prophet_df["ds"] <= train_fin)
    ].copy()

    if len(train) == 0:
        LOGGER.warning("Zona %s: sin datos en la ventana de entrenamiento", zona_num)
        return None, None

    for col in REGRESSORS:
        if col in train.columns and train[col].isnull().sum() > 0:
            train[col] = train[col].fillna(train[col].mean())

    LOGGER.info(
        "Zona %s: entrenando %s registros (%s → %s)",
        zona_num, len(train),
        train["ds"].min().date(),
        train["ds"].max().date(),
    )

    m = Prophet(**PROPHET_PARAMS)
    for reg in REGRESSORS:
        m.add_regressor(reg)
    m.fit(train)

    LOGGER.info("Zona %s: entrenamiento completado", zona_num)
    return m, train


def run_training_pipeline(datasets: dict,
                          fecha_prediccion: pd.Timestamp) -> dict:
    """
    Entrena Prophet para todas las zonas.
    Devuelve dict {zona_num: (modelo, train_df)}.
    """
    modelos = {}

    for zona_num, prophet_df in datasets.items():
        config = ZONAS_PLIEGO[zona_num]
        LOGGER.info("── Zona %s: %s ──", zona_num, config["nombre"])

        modelo, train = train_zona(zona_num, prophet_df, fecha_prediccion)

        if modelo is None:
            LOGGER.warning("Zona %s: sin modelo — omitida", zona_num)
            continue

        modelos[zona_num] = (modelo, train)

    LOGGER.info("Entrenamiento completado: %s modelos", len(modelos))
    return modelos


def main(datasets: dict, fecha_prediccion: pd.Timestamp,
         engine=None) -> dict:
    return run_training_pipeline(datasets, fecha_prediccion)