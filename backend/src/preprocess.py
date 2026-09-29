"""
preprocess.py — CU#48 Burgos
Limpieza de datos, construcción de pre-series por sensor y
series temporales por zona del pliego con variables exógenas.
"""

import logging
import math

import holidays
import numpy as np
import pandas as pd

from config import (
    BURGOS_LAT,
    BURGOS_LON,
    CSV_AEMET_NEW,
    CSV_AEMET_OLD,
    CSV_EVENTOS_AYTO,
    CSV_EVENTOS_JCYL_NEW,
    CSV_EVENTOS_JCYL_OLD,
    CSV_SEEKETING_HISTORICO,
    CSV_SEEKETING_NUEVO,
    CSV_SEEKETING_ZONAS,
    FESTIVOS_LOCALES,
    RADIO_EVENTOS_KM,
    REGRESSORS,
    SENSORES_COORDS,
    UMBRAL_SOL,
    ZONAS_PLIEGO,
    get_train_ini,
)

LOGGER = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def distancia_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def fotoperiodo_horas(fecha, lat_deg=BURGOS_LAT) -> float:
    lat_rad = math.radians(lat_deg)
    dia_año = fecha.timetuple().tm_yday
    decl    = math.radians(23.45 * math.sin(math.radians(360 / 365 * (dia_año - 81))))
    cos_ha  = max(-1, min(1, -math.tan(lat_rad) * math.tan(decl)))
    return 2 * math.degrees(math.acos(cos_ha)) / 15


def normalizar_nombre(nombre: str) -> str:
    nombre = nombre.strip().lower()
    for src, tgt in [(" ", "_"), (".", ""), ("/", "_"), ("á", "a"), ("é", "e"),
                     ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")]:
        nombre = nombre.replace(src, tgt)
    return nombre.strip("_")


# ── Carga de datos con fallback CSV ──────────────────────────────────────────

def load_seeketing(df_bbdd: pd.DataFrame | None) -> pd.DataFrame:
    """Carga y unifica Seeketing desde BBDD o CSVs de fallback."""
    if df_bbdd is not None:
        LOGGER.info("Seeketing cargado desde BBDD")
        return df_bbdd

    LOGGER.info("Seeketing: usando CSVs de fallback")

    zonas = pd.read_csv(CSV_SEEKETING_ZONAS)
    zonas = zonas[["id", "name"]].copy()

    old = pd.read_csv(CSV_SEEKETING_HISTORICO, sep=";", encoding="latin1")
    old["zone_id"]   = old["zone_id"].astype(str).str.replace(".", "", regex=False).astype(int)
    old["timestamp"] = pd.to_datetime(old["timestamp"], errors="coerce")

    new = pd.read_csv(CSV_SEEKETING_NUEVO)
    new["zone_id"]   = new["zone_id"].astype(str).str.replace(".", "", regex=False).astype(int)
    new["timestamp"] = pd.to_datetime(new["timestamp"].str[:19], errors="coerce")

    cols = ["zone_id", "timestamp", "visits", "new_visits",
            "recurrents", "visitors_unique", "visittime_avg", "presencetime_avg"]
    old = old[cols].copy()
    new = new[[c for c in cols if c in new.columns]].copy()

    df = (pd.concat([old, new], ignore_index=True)
          .sort_values("visitors_unique", ascending=False)
          .drop_duplicates(subset=["zone_id", "timestamp"], keep="first")
          .sort_values(["zone_id", "timestamp"])
          .reset_index(drop=True))

    df["zone_id"] = df["zone_id"].replace(3655, 36550)
    for col in ["visits", "new_visits", "recurrents", "visitors_unique"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").round().fillna(0).astype(int)
        df[col] = df[col].clip(lower=0)

    df = df.merge(zonas, left_on="zone_id", right_on="id", how="left")
    df["name"] = df["name"].fillna("Sensor_" + df["zone_id"].astype(str))
    df = df.drop(columns=["id"], errors="ignore")

    LOGGER.info("Seeketing unificado: %s registros, %s zonas",
                len(df), df["zone_id"].nunique())
    return df


def load_aemet(df_bbdd: pd.DataFrame | None) -> pd.DataFrame:
    """Carga y unifica AEMET desde BBDD o CSVs de fallback."""
    if df_bbdd is not None:
        LOGGER.info("AEMET cargado desde BBDD")
        return df_bbdd

    LOGGER.info("AEMET: usando CSVs de fallback")

    old = pd.read_csv(CSV_AEMET_OLD)
    new = pd.read_csv(CSV_AEMET_NEW)
    old["fecha"] = pd.to_datetime(old["time"].str[:10])
    new["fecha"] = pd.to_datetime(new["time"].str[:10])

    cols = ["fecha", "tmed", "tmin", "tmax", "prec",
            "hrMedia", "hrMin", "hrMax", "presMin", "presMax",
            "velmedia", "racha", "sol"]

    aemet = (pd.concat([old[cols], new[cols]], ignore_index=True)
             .drop_duplicates(subset=["fecha"], keep="last")
             .sort_values("fecha")
             .reset_index(drop=True))

    for col in ["prec", "presMin", "presMax"]:
        aemet[col] = aemet[col].interpolate(method="linear").round(1)

    LOGGER.info("AEMET unificado: %s registros", len(aemet))
    return aemet


def load_eventos(df_bbdd: pd.DataFrame | None) -> pd.DataFrame:
    """Carga y unifica eventos desde BBDD o CSVs de fallback."""
    if df_bbdd is not None:
        LOGGER.info("Eventos cargados desde BBDD")
        return df_bbdd

    LOGGER.info("Eventos: usando CSVs de fallback")

    old = pd.read_csv(CSV_EVENTOS_JCYL_OLD)
    new = pd.read_csv(CSV_EVENTOS_JCYL_NEW)
    if "ontology" not in old.columns:
        old["ontology"] = None
    old["fuente"] = "jcyl_old"
    new["fuente"] = "jcyl_new"
    jcyl = (pd.concat([new, old], ignore_index=True)
            .drop_duplicates(subset=["id_event"], keep="first"))

    ayto = pd.read_csv(CSV_EVENTOS_AYTO)
    ayto["fuente"] = "ayuntamiento"

    GPS_POR_LOCATION = {
        "sala de exposiciones del Arco de Santa María":    (42.3402, -3.6985),
        "sala de exposiciones del Monasterio de San Juan": (42.3448, -3.6989),
        "sala de exposiciones del Teatro Principal":       (42.3432, -3.6968),
        "Teatro Principal de Burgos":                      (42.3432, -3.6968),
        "Calle Serramagna, 10":                            (42.3432, -3.7173),
        "calle calzadas 1, burgos":                        (42.3440, -3.7020),
    }
    for idx, row in ayto[ayto["gps_latitude"].isnull()].iterrows():
        loc = row["location"]
        if loc in GPS_POR_LOCATION:
            lat, lon = GPS_POR_LOCATION[loc]
            ayto.loc[idx, "gps_latitude"]  = lat
            ayto.loc[idx, "gps_longitude"] = lon

    cols_comunes = ["title", "category", "start_date", "end_date",
                    "gps_latitude", "gps_longitude", "fuente"]
    jcyl_clean = jcyl[["title", "category", "start_date", "end_date",
                        "gps_latitude", "gps_longitude", "fuente"]].copy()
    ayto_clean = ayto.rename(columns={"type": "category"})[cols_comunes].copy()

    for df_ev in [jcyl_clean, ayto_clean]:
        df_ev["start_date"] = pd.to_datetime(df_ev["start_date"])
        df_ev["end_date"]   = pd.to_datetime(df_ev["end_date"])

    eventos = pd.concat([jcyl_clean, ayto_clean], ignore_index=True)
    eventos = eventos[
        eventos.apply(lambda r: distancia_km(
            r["gps_latitude"], r["gps_longitude"],
            BURGOS_LAT, BURGOS_LON) < 5.0, axis=1)
    ].sort_values("start_date").reset_index(drop=True)

    LOGGER.info("Eventos unificados (Burgos ciudad): %s registros", len(eventos))
    return eventos


# ── Detección de sensor_down ──────────────────────────────────────────────────

def detectar_sensor_down(serie: pd.Series, ventana: int = 24,
                         min_media: float = 5) -> pd.Series:
    """
    sensor_down=1 cuando visitors_unique==0 y la media móvil de las
    últimas ventana horas supera min_media.
    Los ceros nocturnos legítimos NO se marcan.
    """
    media_movil = serie.rolling(window=ventana, min_periods=1).mean().shift(1)
    return ((serie == 0) & (media_movil > min_media)).astype(int)


# ── Pre-series por sensor ─────────────────────────────────────────────────────

def build_preseries(df_seek: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Construye serie horaria completa por sensor con huecos a 0 y sensor_down.
    Devuelve dict {nombre_normalizado: dataframe}.
    """
    preseries = {}
    for nombre in df_seek["name"].dropna().unique():
        sub = df_seek[df_seek["name"] == nombre].sort_values("timestamp")
        serie_completa = pd.DataFrame(
            pd.date_range(sub["timestamp"].min(),
                          sub["timestamp"].max(), freq="h"),
            columns=["timestamp"],
        )
        sub_full = serie_completa.merge(
            sub[["timestamp", "visitors_unique"]], on="timestamp", how="left"
        )
        sub_full["visitors_unique"] = sub_full["visitors_unique"].fillna(0).astype(int)
        sub_full["sensor_down"]     = detectar_sensor_down(sub_full["visitors_unique"])

        key = normalizar_nombre(nombre)
        preseries[key] = sub_full[["timestamp", "visitors_unique", "sensor_down"]]

    LOGGER.info("Pre-series generadas: %s sensores", len(preseries))
    return preseries


# ── Expansión horaria AEMET ───────────────────────────────────────────────────

def build_aemet_horario(aemet: pd.DataFrame) -> pd.DataFrame:
    """
    Expande datos diarios de AEMET a granularidad horaria.
    Temperatura sinusoidal, lluvia y sol binarios, resto constantes.
    """
    rows = []
    for _, dia in aemet.iterrows():
        fecha = dia["fecha"]
        horas = pd.date_range(fecha, periods=24, freq="h")

        hora_arr = np.arange(24)
        amp      = (dia["tmax"] - dia["tmin"]) / 2
        centro   = (dia["tmax"] + dia["tmin"]) / 2
        desfase  = 15 * (2 * np.pi / 24)
        temps    = centro + amp * np.sin((hora_arr * 2 * np.pi / 24) - desfase + np.pi / 2)

        horas_luz   = fotoperiodo_horas(fecha)
        pct_sol     = dia["sol"] / horas_luz if horas_luz > 0 else 0
        dia_soleado = 1 if pct_sol >= UMBRAL_SOL else 0
        lluvia      = 1 if dia["prec"] > 0 else 0

        for i, h in enumerate(horas):
            rows.append({
                "timestamp":   h,
                "temp_c":      round(temps[i], 2),
                "lluvia":      lluvia,
                "dia_soleado": dia_soleado,
                "hr_media":    dia["hrMedia"],
                "velmedia_ms": dia["velmedia"],
            })

    df_aemet_h = pd.DataFrame(rows)
    LOGGER.info("AEMET horario: %s registros", len(df_aemet_h))
    return df_aemet_h


# ── Pre-series de eventos ─────────────────────────────────────────────────────

def build_eventos_por_zona(eventos: pd.DataFrame,
                           rango_ini: pd.Timestamp,
                           rango_fin: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """
    Genera serie horaria con hay_evento=1 para cada sensor
    en días con evento a menos de RADIO_EVENTOS_KM.
    """
    serie_horaria = pd.date_range(rango_ini, rango_fin, freq="h")

    asignaciones = {}
    for _, ev in eventos.iterrows():
        for sensor_nombre, (zlat, zlon) in SENSORES_COORDS.items():
            dist = distancia_km(ev["gps_latitude"], ev["gps_longitude"], zlat, zlon)
            if dist <= RADIO_EVENTOS_KM:
                if sensor_nombre not in asignaciones:
                    asignaciones[sensor_nombre] = set()
                asignaciones[sensor_nombre].add(ev["start_date"].date())

    eventos_por_zona = {}
    for sensor_nombre in SENSORES_COORDS:
        fechas_evento = asignaciones.get(sensor_nombre, set())
        df_ev = pd.DataFrame({"timestamp": serie_horaria})
        df_ev["hay_evento"] = df_ev["timestamp"].dt.date.isin(
            fechas_evento).astype(int)
        eventos_por_zona[sensor_nombre] = df_ev

    LOGGER.info("Pre-series de eventos generadas: %s zonas", len(eventos_por_zona))
    return eventos_por_zona


# ── Agregación de sensores por zona del pliego ────────────────────────────────

def agregar_zona(config: dict,
                 preseries: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Construye la serie temporal de una zona aplicando la lógica
    de agregación y escalado en caídas de sensor.
    Añade columna modo_calculo: 'normal' | 'respaldo' | 'ambos_caidos'
    """
    modo      = config.get("modo", "unico")
    principal = preseries.get(config["principal"])

    if principal is None:
        LOGGER.warning("Sensor principal '%s' no encontrado", config["principal"])
        return pd.DataFrame(
            columns=["timestamp", "visitors_unique", "sensor_down", "modo_calculo"])

    if modo == "unico" or config.get("respaldo") is None:
        serie = principal[["timestamp", "visitors_unique", "sensor_down"]].copy()
        serie["modo_calculo"] = "normal"
        return serie

    respaldo = preseries.get(config["respaldo"])
    if respaldo is None:
        LOGGER.warning("Sensor de respaldo '%s' no encontrado — usando solo principal",
                       config["respaldo"])
        serie = principal[["timestamp", "visitors_unique", "sensor_down"]].copy()
        serie["modo_calculo"] = "normal"
        return serie

    merged = principal[["timestamp", "visitors_unique", "sensor_down"]].merge(
        respaldo[["timestamp", "visitors_unique", "sensor_down"]],
        on="timestamp", how="outer", suffixes=("_p", "_r"),
    ).fillna(0).sort_values("timestamp").reset_index(drop=True)

    if modo == "suma":
        def calcular_suma(row):
            p_down = row["sensor_down_p"] == 1
            r_down = row["sensor_down_r"] == 1
            if not p_down and not r_down:
                return row["visitors_unique_p"] + row["visitors_unique_r"], 0, "normal"
            elif p_down and not r_down:
                return round(row["visitors_unique_r"] * config["factor_sin_principal"]), 1, "respaldo"
            elif not p_down and r_down:
                return round(row["visitors_unique_p"] * config["factor_sin_respaldo"]), 1, "respaldo"
            else:
                return 0, 1, "ambos_caidos"
        resultados = merged.apply(calcular_suma, axis=1, result_type="expand")

    elif modo == "principal_respaldo":
        def calcular_respaldo(row):
            p_down = row["sensor_down_p"] == 1
            r_down = row["sensor_down_r"] == 1
            if not p_down:
                return row["visitors_unique_p"], 0, "normal"
            elif not r_down:
                return round(row["visitors_unique_r"] * config["factor_respaldo"]), 1, "respaldo"
            else:
                return 0, 1, "ambos_caidos"
        resultados = merged.apply(calcular_respaldo, axis=1, result_type="expand")

    resultados.columns = ["visitors_unique", "sensor_down", "modo_calculo"]
    serie = pd.concat([merged[["timestamp"]], resultados], axis=1)
    serie["visitors_unique"] = serie["visitors_unique"].astype(int)
    serie["sensor_down"]     = serie["sensor_down"].astype(int)
    return serie


# ── Dataset model-ready por zona ──────────────────────────────────────────────

def build_dataset_zona(zona_num: int, config: dict,
                       preseries: dict,
                       aemet_h: pd.DataFrame,
                       eventos_zona: pd.DataFrame) -> pd.DataFrame:
    """
    Une serie de zona + AEMET + eventos + festivos.
    Devuelve dataframe en formato Prophet (ds, y + regressors).
    """
    serie = agregar_zona(config, preseries)
    if len(serie) == 0:
        return pd.DataFrame()

    festivos_dict = {}
    años = serie["timestamp"].dt.year.unique()
    for year in años:
        festivos_dict.update(holidays.Spain(prov="CL", years=int(year)))
    for fecha_str, nombre in FESTIVOS_LOCALES.items():
        festivos_dict[pd.Timestamp(fecha_str).date()] = nombre

    festivos_df = pd.DataFrame({"timestamp": serie["timestamp"]})
    festivos_df["es_festivo"] = festivos_df["timestamp"].dt.date.map(
        lambda d: 1 if d in festivos_dict else 0)

    df = (serie
          .merge(aemet_h,    on="timestamp", how="left")
          .merge(eventos_zona[["timestamp", "hay_evento"]], on="timestamp", how="left")
          .merge(festivos_df, on="timestamp", how="left"))

    cols_aemet = ["temp_c", "lluvia", "dia_soleado", "hr_media", "velmedia_ms"]
    for col in cols_aemet:
        if df[col].isnull().sum() > 0:
            df[col] = df[col].fillna(df[col].mean()).round(2)

    df["hay_evento"] = df["hay_evento"].fillna(0).astype(int)
    df["es_festivo"] = df["es_festivo"].fillna(0).astype(int)

    prophet_df = df.rename(columns={
        "timestamp":       "ds",
        "visitors_unique": "y",
    })[["ds", "y"] + REGRESSORS].copy()

    LOGGER.debug("Dataset zona %s: %s registros", zona_num, len(prophet_df))
    return prophet_df


def build_all_datasets(df_seek_bbdd, df_aemet_bbdd,
                       df_eventos_bbdd) -> dict:
    """
    Pipeline completo de preprocesado.
    Devuelve dict {zona_num: prophet_df}.
    """
    LOGGER.info("Iniciando preprocesado de datos")

    seek    = load_seeketing(df_seek_bbdd)
    aemet   = load_aemet(df_aemet_bbdd)
    eventos = load_eventos(df_eventos_bbdd)

    preseries = build_preseries(seek)
    aemet_h   = build_aemet_horario(aemet)

    rango_ini = seek["timestamp"].min()
    rango_fin = seek["timestamp"].max()

    eventos_por_zona = build_eventos_por_zona(eventos, rango_ini, rango_fin)

    datasets = {}
    for zona_num, config in ZONAS_PLIEGO.items():
        sensor_nombre = config["principal"]
        eventos_zona  = eventos_por_zona.get(
            sensor_nombre,
            pd.DataFrame({
                "timestamp": pd.date_range(rango_ini, rango_fin, freq="h"),
                "hay_evento": 0,
            })
        )
        df_zona = build_dataset_zona(
            zona_num, config, preseries, aemet_h, eventos_zona)

        if len(df_zona) > 0:
            datasets[zona_num] = df_zona
            LOGGER.info("Zona %s lista: %s registros", zona_num, len(df_zona))

    LOGGER.info("Preprocesado completado: %s zonas", len(datasets))
    return datasets