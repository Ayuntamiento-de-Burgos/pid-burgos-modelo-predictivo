"""
api.py — Módulo Sinergia · Modelo Predictivo (API REST)

Expone al frontal Angular los resultados del modelo y la configuración de
personalización. No entrena ni predice (de eso se encarga el job diario,
entrypoint.sh); esta API solo LEE los resultados ya calculados.

Endpoints:
    GET /api/health       -> estado
    GET /api/branding     -> config/branding/branding.json (personalización)
    GET /api/zones        -> zonas del destino
    GET /api/predictions  -> predicciones (?zone=&from=&to=)
    GET /api/history      -> histórico real (?zone=&from=&to=)
"""

import json
import logging
from datetime import date

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

import config
from database import get_engine_lectura

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Módulo Sinergia · Modelo Predictivo", version="1.0.0")

# CORS abierto: el frontal se sirve por nginx con proxy /api, pero en desarrollo
# (ng serve) conviene permitir el origen local.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

SCHEMA = config.DB_SCHEMA_OUTPUT


def _read_table(table: str, value_col: str, zone: int | None,
                desde: str | None, hasta: str | None) -> list[dict]:
    """Lee una tabla de salida (predictions/prediction_historic). Si no hay
    BBDD, cae al CSV de results/ generado por el job."""
    engine = get_engine_lectura()
    if engine is not None:
        try:
            q = f'SELECT timestamp, zone_num, zone_name, "{value_col}" ' \
                f'FROM "{SCHEMA}"."{table}" WHERE 1=1'
            params: dict = {}
            if zone is not None:
                q += " AND zone_num = %(z)s"; params["z"] = zone
            if desde:
                q += " AND timestamp >= %(d)s"; params["d"] = desde
            if hasta:
                q += " AND timestamp <= %(h)s"; params["h"] = hasta
            q += " ORDER BY zone_num, timestamp"
            df = pd.read_sql(q, engine, params=params)
        finally:
            engine.dispose()
    else:
        fallback = config.RESULTS_DIR / (
            "predicciones_fallback.csv" if value_col == "visitor_prediction"
            else "historico_fallback.csv")
        if not fallback.exists():
            return []
        df = pd.read_csv(fallback)
        if zone is not None:
            df = df[df["zone_num"] == zone]
    df["timestamp"] = pd.to_datetime(df["timestamp"]).astype(str)
    return df.to_dict(orient="records")


@app.get("/api/health")
def health():
    return {"status": "ok", "schema": SCHEMA, "zonas": len(config.ZONAS_PLIEGO)}


@app.get("/api/branding")
def branding():
    path = config.CONFIG_DIR / "branding" / "branding.json"
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


@app.get("/api/zones")
def zones():
    return [
        {"num": num, "nombre": z.get("nombre"), "label": z.get("label")}
        for num, z in sorted(config.ZONAS_PLIEGO.items())
    ]


@app.get("/api/predictions")
def predictions(zone: int | None = Query(None), from_: str | None = Query(None, alias="from"),
                to: str | None = Query(None)):
    return _read_table(config.DB_TABLE_PREDICCIONES, "visitor_prediction", zone, from_, to)


@app.get("/api/history")
def history(zone: int | None = Query(None), from_: str | None = Query(None, alias="from"),
            to: str | None = Query(None)):
    return _read_table(config.DB_TABLE_HISTORICO, "visitors", zone, from_, to)
