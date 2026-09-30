"""
config.py — Módulo Sinergia · Modelo Predictivo

Configuración central del pipeline. A diferencia del CU48 original (donde todo
estaba hardcodeado), aquí TODO lo específico del destino se carga desde ficheros
externos editables sin tocar código:

    config/model.json       -> parámetros del modelo, ciudad, festivos
    config/zones.json       -> zonas del destino y su mapeo a sensores
    config/connectors.json  -> esquemas/tablas de entrada y salida (los conectores del destino)

La carpeta de config se resuelve por la variable de entorno CONFIG_DIR
(por defecto <repo>/config). Los CSVs de datos de ejemplo viven en backend/data
y se usan como fallback si no hay BBDD.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

# ── Rutas ─────────────────────────────────────────────────────────────────────
SRC_DIR      = Path(__file__).resolve().parent
BACKEND_ROOT = SRC_DIR.parent
REPO_ROOT    = BACKEND_ROOT.parent
DATA_DIR     = BACKEND_ROOT / "data"
RESULTS_DIR  = Path(os.getenv("RESULTS_DIR", BACKEND_ROOT / "results"))
CONFIG_DIR   = Path(os.getenv("CONFIG_DIR", REPO_ROOT / "config"))


def _load_json(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró {path}. Define CONFIG_DIR o copia la carpeta config/.")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_MODEL      = _load_json("model.json")
_ZONES      = _load_json("zones.json")
_CONNECTORS = _load_json("connectors.json")

# ── CSVs de fallback (datos de ejemplo Burgos, en backend/data) ───────────────
CSV_SEEKETING_HISTORICO  = DATA_DIR / "Seeketing_visitas_histórico.csv"
CSV_SEEKETING_NUEVO      = DATA_DIR / "seeketing_zone_visits_202606221338.csv"
CSV_SEEKETING_ZONAS      = DATA_DIR / "seeketing_zone_202606161300.csv"
CSV_AEMET_OLD            = DATA_DIR / "aemetforecast_202605290914.csv"
CSV_AEMET_NEW            = DATA_DIR / "aemetforecast_202606161128.csv"
CSV_EVENTOS_JCYL_OLD     = DATA_DIR / "jcyl_eventos_202605290914.csv"
CSV_EVENTOS_JCYL_NEW     = DATA_DIR / "jcyl_eventos_202606161129.csv"
CSV_EVENTOS_AYTO         = DATA_DIR / "eventos_202606161129.csv"

# ── Modo BBDD (desde connectors.json) ─────────────────────────────────────────
BBDD_LECTURA   = bool(_CONNECTORS.get("read_enabled", True))
BBDD_ESCRITURA = bool(_CONNECTORS.get("write_enabled", True))

# ── Esquemas y tablas (desde connectors.json) ─────────────────────────────────
_TABLES = _CONNECTORS["tables"]
DB_SCHEMA_INPUT          = _CONNECTORS.get("input_schema", "silver_tourism")
DB_SCHEMA_OUTPUT         = _CONNECTORS.get("output_schema", DB_SCHEMA_INPUT)
DB_TABLE_SEEKETING       = _TABLES["afluencia_visitas"]
DB_TABLE_SEEKETING_ZONAS = _TABLES["afluencia_zonas"]
DB_TABLE_AEMET           = _TABLES["meteo"]
DB_TABLE_EVENTOS_AYTO    = _TABLES.get("eventos_local")
DB_TABLE_EVENTOS_JCYL    = _TABLES.get("eventos_regional")
DB_TABLE_PREDICCIONES    = _TABLES["salida_predicciones"]
DB_TABLE_HISTORICO       = _TABLES["salida_historico"]
AEMET_ESTACION           = (_CONNECTORS.get("meteo") or {}).get("estacion")

# ── Credenciales BBDD (.env) ──────────────────────────────────────────────────
ENV_FILE_VAR   = "MODEL_ENV_FILE"
ENV_CANDIDATES = (
    REPO_ROOT / ".env",
    BACKEND_ROOT / ".env",
    BACKEND_ROOT / "env",
)

# ── Parámetros del modelo (desde model.json) ──────────────────────────────────
FACTOR_K        = float(_MODEL.get("factor_k", 0.563))
PROPHET_PARAMS  = _MODEL["prophet_params"]
REGRESSORS      = list(_MODEL["regressors"])
TRAIN_INI_GLOBAL = pd.Timestamp(_MODEL["train_ini_global"])
VENTANA_MAX_AÑOS = int(_MODEL.get("ventana_max_anos", 2))

# ── Geo / eventos / festivos (desde model.json) ───────────────────────────────
BURGOS_LAT       = float(_MODEL["ciudad"]["lat"])   # centro del municipio
BURGOS_LON       = float(_MODEL["ciudad"]["lon"])
RADIO_EVENTOS_KM = float(_MODEL.get("radio_eventos_km", 1.0))
UMBRAL_SOL       = float(_MODEL.get("umbral_sol", 0.60))
FESTIVOS_LOCALES = dict(_MODEL.get("festivos_locales", {}))

# ── Zonas del destino (desde zones.json) ──────────────────────────────────────
ZONAS_PLIEGO = {int(z["num"]): {k: v for k, v in z.items() if k != "num"}
                for z in _ZONES["zones"]}
SENSORES_COORDS = {k: tuple(v) for k, v in _ZONES.get("sensor_coords", {}).items()}


# ── Funciones auxiliares (idénticas al CU48) ──────────────────────────────────
def resolve_env_file() -> Path | None:
    env_file = os.getenv(ENV_FILE_VAR)
    if env_file:
        return Path(env_file).expanduser().resolve()
    for candidate in ENV_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def get_train_ini(fecha_prediccion: pd.Timestamp,
                  inicio_sensor: pd.Timestamp) -> pd.Timestamp:
    """Inicio efectivo del train: máximo entre el global (todas las exógenas
    disponibles), la ventana móvil de N años y el arranque del sensor."""
    ventana_ini = fecha_prediccion - pd.DateOffset(years=VENTANA_MAX_AÑOS)
    return max(TRAIN_INI_GLOBAL, ventana_ini, inicio_sensor)
