"""
database.py — Módulo Sinergia · Modelo Predictivo

Conexión a PostgreSQL con engines separados de lectura/escritura. Si no hay
credenciales o falla la conexión, devuelve None y el pipeline usa los CSVs de
ejemplo (fallback) o guarda CSV local.

Parametrizado por config/connectors.json: esquemas, tablas, estación meteo y
qué fuentes de eventos existen (opcionales). La afluencia es obligatoria; los
eventos y el filtro de estación meteo son opcionales.
"""

import logging
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

from config import (
    AEMET_ESTACION,
    BBDD_ESCRITURA,
    BBDD_LECTURA,
    DB_SCHEMA_INPUT,
    DB_SCHEMA_OUTPUT,
    DB_TABLE_AEMET,
    DB_TABLE_EVENTOS_AYTO,
    DB_TABLE_EVENTOS_JCYL,
    DB_TABLE_HISTORICO,
    DB_TABLE_PREDICCIONES,
    DB_TABLE_SEEKETING,
    DB_TABLE_SEEKETING_ZONAS,
    RESULTS_DIR,
    resolve_env_file,
)

LOGGER = logging.getLogger(__name__)
_ENV_LOADED = False


def load_database_environment() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_file = resolve_env_file()
    if env_file is not None:
        load_dotenv(env_file, override=False)
        LOGGER.info("Configuración cargada desde %s", env_file)
    else:
        LOGGER.info("No se encontró .env — usando variables de entorno del sistema")
    _ENV_LOADED = True


def _build_engine(user, password, host, port, db_name, tag):
    if not all([user, password, host, port, db_name]):
        LOGGER.warning("Credenciales incompletas para engine %s — modo CSV", tag)
        return None
    try:
        engine = create_engine(
            f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}",
            pool_pre_ping=True,
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        LOGGER.info("Engine %s conectado (%s:%s/%s)", tag, host, port, db_name)
        return engine
    except Exception as exc:
        LOGGER.warning("No se pudo conectar engine %s: %s — modo CSV", tag, exc)
        return None


def _engine(tag: str, read: bool):
    load_database_environment()
    suffix = "READ" if read else "WRITE"
    user     = os.getenv(f"DB_USER_{suffix}") or os.getenv("DB_USER")
    password = (os.getenv(f"DB_PASS_{suffix}") or os.getenv("DB_PASS")
                or os.getenv("DB_PASSWORD"))
    host     = os.getenv("DB_HOST")
    port     = os.getenv("DB_PORT")
    db_name  = os.getenv("DB_NAME")
    return _build_engine(user, password, host, port, db_name, tag=tag)


def get_engine_lectura():
    if not BBDD_LECTURA:
        LOGGER.info("read_enabled=false — usando CSVs de ejemplo")
        return None
    return _engine("LECTURA", read=True)


def get_engine_escritura():
    if not BBDD_ESCRITURA:
        LOGGER.info("write_enabled=false — resultados solo en CSV local")
        return None
    return _engine("ESCRITURA", read=False)


# ── Lectura de datos de entrada ───────────────────────────────────────────────

def read_seeketing(engine) -> pd.DataFrame | None:
    if engine is None:
        return None
    try:
        query = f"""
            SELECT v.zone_id, v.timestamp, v.visits, v.new_visits, v.recurrents,
                   v.visitors_unique, v.visittime_avg, v.presencetime_avg, z.name
            FROM {DB_SCHEMA_INPUT}.{DB_TABLE_SEEKETING} v
            LEFT JOIN {DB_SCHEMA_INPUT}.{DB_TABLE_SEEKETING_ZONAS} z
                ON v.zone_id = z.id
        """
        df = pd.read_sql(query, engine)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        LOGGER.info("Afluencia leída desde BBDD: %s registros", len(df))
        return df
    except Exception as exc:
        LOGGER.warning("Error leyendo afluencia de BBDD: %s", exc)
        return None
    finally:
        engine.dispose()


def read_aemet(engine) -> pd.DataFrame | None:
    if engine is None:
        return None
    try:
        where = f"WHERE name = '{AEMET_ESTACION}'" if AEMET_ESTACION else ""
        query = f"""
            SELECT DATE(time AT TIME ZONE 'Europe/Madrid') AS fecha,
                   tmed, tmin, tmax, prec, "hrMedia", "hrMin", "hrMax",
                   "presMin", "presMax", velmedia, racha, sol
            FROM {DB_SCHEMA_INPUT}.{DB_TABLE_AEMET}
            {where}
            ORDER BY fecha
        """
        df = pd.read_sql(query, engine)
        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.drop_duplicates(subset=["fecha"], keep="last").reset_index(drop=True)
        LOGGER.info("Meteo leída desde BBDD: %s registros", len(df))
        return df
    except Exception as exc:
        LOGGER.warning("Error leyendo meteo de BBDD: %s", exc)
        return None
    finally:
        engine.dispose()


def read_eventos(engine) -> pd.DataFrame | None:
    """Combina las fuentes de eventos configuradas. Ambas son opcionales:
    si en connectors.json están a null, se omiten. Sin ninguna → DataFrame vacío."""
    if engine is None:
        return None
    cols = ["id", "title", "category", "venue_of_celebration",
            "start_date", "end_date", "gps_longitude", "gps_latitude", "fuente"]
    frames = []
    try:
        if DB_TABLE_EVENTOS_AYTO:
            frames.append(pd.read_sql(f"""
                SELECT id, title, type AS category, location AS venue_of_celebration,
                       start_date::date AS start_date, end_date::date AS end_date,
                       gps_longitude, gps_latitude, 'local' AS fuente
                FROM {DB_SCHEMA_INPUT}.{DB_TABLE_EVENTOS_AYTO}
                WHERE gps_latitude IS NOT NULL OR location IS NOT NULL
            """, engine))
        if DB_TABLE_EVENTOS_JCYL:
            frames.append(pd.read_sql(f"""
                SELECT id::text AS id, title, category, venue_of_celebration,
                       start_date, end_date, gps_longitude, gps_latitude,
                       'regional' AS fuente
                FROM {DB_SCHEMA_INPUT}.{DB_TABLE_EVENTOS_JCYL}
                WHERE gps_latitude IS NOT NULL
            """, engine))
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
        if not df.empty:
            df["start_date"] = pd.to_datetime(df["start_date"])
            df["end_date"]   = pd.to_datetime(df["end_date"])
        LOGGER.info("Eventos leídos desde BBDD: %s registros", len(df))
        return df
    except Exception as exc:
        LOGGER.warning("Error leyendo eventos de BBDD: %s", exc)
        return None
    finally:
        engine.dispose()


# ── Escritura de resultados ───────────────────────────────────────────────────

def _upsert(df_bbdd, engine, table, fallback_path):
    if engine is None:
        LOGGER.warning("Sin engine de escritura — guardando %s", fallback_path)
        df_bbdd.to_csv(fallback_path, index=False)
        return df_bbdd
    try:
        inspector = inspect(engine)
        existe = inspector.has_table(table, schema=DB_SCHEMA_OUTPUT)
        if existe:
            existing = pd.read_sql_table(table, engine, schema=DB_SCHEMA_OUTPUT)
            existing["timestamp"] = pd.to_datetime(existing["timestamp"])
            key = ["timestamp", "zone_num"]
            mask = existing.set_index(key).index.isin(df_bbdd.set_index(key).index)
            combined = pd.concat([existing[~mask], df_bbdd], ignore_index=True)
        else:
            combined = df_bbdd.copy()
        combined = combined.sort_values(["zone_num", "timestamp"]).reset_index(drop=True)
        # TRUNCATE + append (no 'replace'): puede haber matviews dependientes.
        if existe:
            with engine.begin() as conn:
                conn.execute(text(f'TRUNCATE TABLE "{DB_SCHEMA_OUTPUT}"."{table}"'))
                combined.to_sql(table, conn, schema=DB_SCHEMA_OUTPUT,
                                if_exists="append", index=False)
        else:
            combined.to_sql(table, engine, schema=DB_SCHEMA_OUTPUT,
                            if_exists="replace", index=False)
        LOGGER.info("Guardado en BBDD: %s registros en %s.%s",
                    len(combined), DB_SCHEMA_OUTPUT, table)
        return combined
    except Exception as exc:
        LOGGER.error("Error guardando en BBDD (%s): %s", table, exc)
        df_bbdd.to_csv(fallback_path, index=False)
        return df_bbdd
    finally:
        engine.dispose()


def upsert_predicciones(df_new, engine, fallback_path=None):
    fallback_path = fallback_path or str(RESULTS_DIR / "predicciones_fallback.csv")
    df_bbdd = df_new.rename(columns={
        "zona_pliego": "zone_num", "nombre_zona": "zone_name",
        "visitors_unique_predicho": "visitor_prediction",
    })[["timestamp", "zone_num", "zone_name", "visitor_prediction"]].copy()
    return _upsert(df_bbdd, engine, DB_TABLE_PREDICCIONES, fallback_path)


def upsert_historico(df_new, engine, fallback_path=None):
    fallback_path = fallback_path or str(RESULTS_DIR / "historico_fallback.csv")
    df_bbdd = df_new[["timestamp", "zone_num", "zone_name", "visitors"]].copy()
    return _upsert(df_bbdd, engine, DB_TABLE_HISTORICO, fallback_path)
