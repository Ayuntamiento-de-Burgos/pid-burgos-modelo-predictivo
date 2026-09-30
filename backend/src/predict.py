"""
predict.py — CU#48 Burgos
Predicción de flujos turísticos hora a hora por zona del pliego.
Incluye predicción encadenada para salvar gaps sin histórico real.
"""

import logging

import numpy as np
import pandas as pd
from prophet import Prophet

from config import FACTOR_K, REGRESSORS, ZONAS_PLIEGO
from train import mape_diario, mape_periodo

LOGGER = logging.getLogger(__name__)


def _preparar_regressors(horas: pd.DatetimeIndex,
                         prophet_df: pd.DataFrame,
                         train: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara el dataframe de predicción con los regressors.
    Usa valores reales si están en prophet_df, media del train si no.
    """
    future = pd.DataFrame({"ds": horas})

    for col in REGRESSORS:
        datos = prophet_df[
            prophet_df["ds"].isin(horas)
        ][["ds", col]].copy() if col in prophet_df.columns else pd.DataFrame()

        if len(datos) == len(horas):
            future[col] = datos[col].values
        else:
            future[col] = train[col].mean() if col in train.columns else 0

    return future


def predecir_rango(modelo, prophet_df: pd.DataFrame,
                   train: pd.DataFrame,
                   fecha_ini: pd.Timestamp,
                   fecha_fin: pd.Timestamp) -> pd.DataFrame:
    """
    Predice todas las horas del rango [fecha_ini, fecha_fin].
    Si hay un gap entre el último dato del train y fecha_ini,
    rellena día a día de forma encadenada usando predicciones propias.
    """
    train_fin   = train["ds"].max()
    primer_dia  = (train_fin + pd.Timedelta(days=1)).normalize()
    ultimo_dia  = fecha_fin.normalize()

    resultados      = []
    train_extendido = train.copy()

    # Recorrer día a día desde el primer día tras el train hasta fecha_fin
    for dia in pd.date_range(primer_dia, ultimo_dia, freq="D"):
        horas = pd.date_range(dia, periods=24, freq="h")
        future = _preparar_regressors(horas, prophet_df, train_extendido)

        forecast_dia = modelo.predict(future)
        forecast_dia["yhat"] = forecast_dia["yhat"].clip(lower=0)

        # Solo guardar si el día está en el rango objetivo
        if dia >= fecha_ini.normalize():
            resultados.append(forecast_dia[["ds", "yhat", "yhat_lower", "yhat_upper"]])

        # Añadir predicción al histórico para predicción encadenada
        filas_nuevas = pd.DataFrame({
            "ds": forecast_dia["ds"],
            "y":  forecast_dia["yhat"].clip(lower=0),
        })
        for col in REGRESSORS:
            filas_nuevas[col] = future[col].values if col in future.columns else 0

        train_extendido = pd.concat(
            [train_extendido, filas_nuevas], ignore_index=True)

    if not resultados:
        return pd.DataFrame()

    return pd.concat(resultados, ignore_index=True)


def run_prediction_pipeline(datasets: dict, modelos: dict,
                             fecha_ini: str, fecha_fin: str,
                             factor_k: float = FACTOR_K) -> pd.DataFrame:
    """
    Genera predicciones para todas las zonas en [fecha_ini, fecha_fin].
    Devuelve dataframe con las 4 columnas para BBDD.
    """
    fecha_ini_ts = pd.Timestamp(fecha_ini)
    fecha_fin_ts = pd.Timestamp(fecha_fin)

    LOGGER.info("Predicciones %s → %s (Factor K=%.3f)",
                fecha_ini, fecha_fin, factor_k)

    resultados = []
    mapes      = {}

    for zona_num, (modelo, train) in modelos.items():
        config     = ZONAS_PLIEGO[zona_num]
        prophet_df = datasets.get(zona_num)

        if prophet_df is None or modelo is None:
            LOGGER.warning("Zona %s: sin datos o modelo — omitida", zona_num)
            continue

        LOGGER.info("── Prediciendo zona %s: %s ──",
                    zona_num, config["nombre"])

        forecast = predecir_rango(
            modelo=modelo,
            prophet_df=prophet_df,
            train=train,
            fecha_ini=fecha_ini_ts,
            fecha_fin=fecha_fin_ts,
        )

        if len(forecast) == 0:
            LOGGER.warning("Zona %s: sin predicciones generadas", zona_num)
            continue

        # MAPE si hay datos reales en el rango
        real_rango = prophet_df[
            (prophet_df["ds"] >= fecha_ini_ts) &
            (prophet_df["ds"] <= fecha_fin_ts + pd.Timedelta(hours=23))
        ].copy()

        if len(real_rango) > 0:
            mp = round(mape_periodo(real_rango, forecast), 2)
            md = round(mape_diario(real_rango, forecast), 2)
            mapes[zona_num] = {"periodo": mp, "diario_medio": md}
            LOGGER.info("Zona %s: MAPE período=%.2f%% diario_medio=%.2f%%",
                        zona_num, mp, md)

        zona_result = pd.DataFrame({
            "timestamp":                forecast["ds"],
            "zona_pliego":              zona_num,
            "nombre_zona":              config["nombre"],
            "visitors_unique_predicho": (forecast["yhat"] * factor_k)
                                         .clip(lower=0).round(0).astype(int),
        })
        resultados.append(zona_result)
        LOGGER.info("Zona %s: %s predicciones generadas",
                    zona_num, len(zona_result))

    if not resultados:
        LOGGER.warning("No se generaron predicciones para ninguna zona")
        return pd.DataFrame(columns=["timestamp", "zona_pliego",
                                     "nombre_zona", "visitors_unique_predicho"])

    predicciones = pd.concat(resultados, ignore_index=True)

    if mapes:
        LOGGER.info("── Resumen MAPE ──")
        for zona_num, vals in sorted(mapes.items()):
            LOGGER.info("  Zona %s (%s): período=%.2f%% diario_medio=%.2f%%",
                        zona_num, ZONAS_PLIEGO[zona_num]["nombre"],
                        vals["periodo"], vals["diario_medio"])

    LOGGER.info("Predicción completada: %s registros, %s zonas",
                len(predicciones), predicciones["zona_pliego"].nunique())
    return predicciones


def main(datasets: dict, modelos: dict, fecha_ini: str, fecha_fin: str,
         factor_k: float = FACTOR_K, engine=None,
         fallback_path: str | None = None) -> pd.DataFrame:
    from database import upsert_predicciones
    predicciones = run_prediction_pipeline(
        datasets, modelos, fecha_ini, fecha_fin, factor_k)
    if len(predicciones) > 0:
        upsert_predicciones(predicciones, engine, fallback_path=fallback_path)
    return predicciones