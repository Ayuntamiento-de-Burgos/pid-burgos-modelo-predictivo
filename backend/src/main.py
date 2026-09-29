"""
main.py — CU#48 Burgos: Predicción de flujos turísticos
Orquestador principal del pipeline con argparse.

Uso desde la raíz del repositorio:

  Entrenar y predecir (comportamiento por defecto):
    python model_cu48/src/main.py --fecha-ini 2026-07-01 --fecha-fin 2026-07-31

  Predecir un solo día:
    python model_cu48/src/main.py --fecha-ini 2026-07-09 --fecha-fin 2026-07-09

  Sin BBDD (todo local):
    python model_cu48/src/main.py --fecha-ini 2026-07-01 --fecha-fin 2026-07-31 --no-bbdd

  Solo lectura BBDD, escritura en CSV:
    python model_cu48/src/main.py --fecha-ini 2026-07-01 --fecha-fin 2026-07-31 --no-escritura-bbdd

  Factor K personalizado:
    python model_cu48/src/main.py --fecha-ini 2026-07-01 --fecha-fin 2026-07-31 --factor-k 0.8
"""

import argparse
import logging
import sys

import pandas as pd

import config as cfg
from config import FACTOR_K, RESULTS_DIR, ZONAS_PLIEGO, ensure_results_dir, get_train_ini

LOGGER = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def exportar_historico(datasets: dict, fecha_ini: str,
                       factor_k: float,
                       engine_escritura=None) -> None:
    """
    Exporta el histórico real usado para entrenar el modelo.
    Desde train_ini (calculado por get_train_ini) hasta el día anterior
    a fecha_ini. Así prediction_historic contiene exactamente los datos
    sobre los que se basó el modelo para hacer las predicciones.

    Misma lógica que las predicciones:
    - BBDD_ESCRITURA=True  → escribe en silver_tourism.prediction_historic
    - BBDD_ESCRITURA=False → guarda CSV en results/
    - El CSV se genera siempre como backup

    Columnas (idénticas en CSV y BBDD):
        timestamp | zone_num | zone_name | visitors (visitors_unique × Factor K)
    """
    fecha_pred_ts = pd.Timestamp(fecha_ini)
    train_fin_ts  = fecha_pred_ts - pd.Timedelta(days=1)

    rows = []
    for zona_num, prophet_df in datasets.items():
        inicio_sensor = prophet_df["ds"].min()
        train_ini_ts  = get_train_ini(fecha_pred_ts, inicio_sensor)

        real = prophet_df[
            (prophet_df["ds"] >= train_ini_ts) &
            (prophet_df["ds"] <= train_fin_ts + pd.Timedelta(hours=23))
        ].copy()

        if len(real) == 0:
            continue

        rows.append(pd.DataFrame({
            "timestamp": real["ds"],
            "zone_num":  zona_num,
            "zone_name": ZONAS_PLIEGO[zona_num]["nombre"],
            "visitors":  (real["y"] * factor_k).round(0).astype(int),
        }))

    if not rows:
        LOGGER.warning("Sin datos históricos para exportar")
        return

    historico = pd.concat(rows, ignore_index=True)
    historico  = historico.sort_values(
        ["zone_num", "timestamp"]).reset_index(drop=True)

    # ── CSV (siempre) ─────────────────────────────────────────────────────────
    fecha_str = fecha_ini.replace("-", "")
    out_path  = str(RESULTS_DIR / f"historico_{fecha_str}_train.csv")
    historico.to_csv(out_path, index=False)
    LOGGER.info("Histórico de train guardado en CSV: %s registros → %s",
                len(historico), out_path)

    # ── BBDD (si está habilitado) ─────────────────────────────────────────────
    from database import upsert_historico
    upsert_historico(historico, engine_escritura, fallback_path=out_path)


def main() -> None:
    setup_logging()
    ensure_results_dir()

    parser = argparse.ArgumentParser(
        description="Pipeline CU#48 Burgos — predicción de flujos turísticos"
    )
    parser.add_argument("--train",   action="store_true",
                        help="Solo entrenar modelos")
    parser.add_argument("--predict", action="store_true",
                        help="Solo predecir")
    parser.add_argument("--all",     action="store_true",
                        help="Entrenar y predecir (comportamiento por defecto)")
    parser.add_argument("--fecha-ini", type=str, default=None,
                        help="Primer día a predecir (YYYY-MM-DD)")
    parser.add_argument("--fecha-fin", type=str, default=None,
                        help="Último día a predecir (YYYY-MM-DD). "
                             "Igual a fecha-ini para predecir un solo día.")
    parser.add_argument("--factor-k", type=float, default=FACTOR_K,
                        help=f"Factor K dispositivos→personas (default: {FACTOR_K})")
    parser.add_argument("--no-bbdd", action="store_true",
                        help="Desactiva lectura Y escritura en BBDD.")
    parser.add_argument("--no-escritura-bbdd", action="store_true",
                        help="Lee de BBDD pero guarda resultados solo en CSV local.")
    args = parser.parse_args()

    # Comportamiento por defecto: entrenar y predecir
    if not (args.train or args.predict or args.all):
        args.all = True

    # Validar fechas
    if args.predict or args.all:
        if not args.fecha_ini:
            parser.error("--fecha-ini es obligatorio para predecir")
        if not args.fecha_fin:
            args.fecha_fin = args.fecha_ini
            LOGGER.info("--fecha-fin no indicado, usando fecha-ini: %s",
                        args.fecha_ini)

    # ── Flags BBDD ────────────────────────────────────────────────────────────
    if args.no_bbdd:
        cfg.BBDD_LECTURA   = False
        cfg.BBDD_ESCRITURA = False
        LOGGER.info("Modo sin BBDD: todo en local")
    elif args.no_escritura_bbdd:
        cfg.BBDD_ESCRITURA = False
        LOGGER.info("Modo solo lectura BBDD: escritura en CSV local")

    # ── Engines ───────────────────────────────────────────────────────────────
    from database import (get_engine_escritura, get_engine_lectura,
                          read_aemet, read_eventos, read_seeketing)

    engine_lectura   = get_engine_lectura()
    engine_escritura = get_engine_escritura()

    LOGGER.info("Lectura: %s",
                "BBDD" if engine_lectura else "CSVs locales")
    LOGGER.info("Escritura: %s",
                "BBDD + CSV" if engine_escritura else "solo CSV")

    # ── Preprocesado ──────────────────────────────────────────────────────────
    LOGGER.info("Cargando y preprocesando datos")
    from preprocess import build_all_datasets

    df_seek    = read_seeketing(engine_lectura)
    df_aemet   = read_aemet(engine_lectura)
    df_eventos = read_eventos(engine_lectura)
    datasets   = build_all_datasets(df_seek, df_aemet, df_eventos)
    LOGGER.info("Datasets listos: %s zonas", len(datasets))

    # ── Histórico del train ───────────────────────────────────────────────────
    # Exporta el histórico real usado para entrenar:
    # desde train_ini hasta el día anterior a fecha_ini.
    # BBDD_ESCRITURA=True  → escribe en silver_tourism.prediction_historic
    # BBDD_ESCRITURA=False → guarda CSV en results/
    # CSV se genera siempre como backup
    # Columnas: timestamp | zone_num | zone_name | visitors (× Factor K)
    if args.fecha_ini:
        exportar_historico(
            datasets=datasets,
            fecha_ini=args.fecha_ini,
            factor_k=args.factor_k,
            engine_escritura=engine_escritura,
        )

    # ── Entrenamiento ─────────────────────────────────────────────────────────
    modelos = {}

    if args.train or args.all:
        from train import main as train_main
        fecha_pred = pd.Timestamp(args.fecha_ini)
        LOGGER.info("Iniciando entrenamiento hasta %s",
                    (fecha_pred - pd.Timedelta(days=1)).date())
        modelos = train_main(
            datasets=datasets,
            fecha_prediccion=fecha_pred,
            engine=engine_escritura,
        )

    elif args.predict:
        LOGGER.warning(
            "--predict sin --train: no hay modelos disponibles. "
            "Usa --all o --train para entrenar primero.")

    # ── Predicción ────────────────────────────────────────────────────────────
    if (args.predict or args.all) and modelos:
        from predict import main as predict_main
        fecha_str     = (args.fecha_ini.replace("-", "") + "_" +
                         args.fecha_fin.replace("-", ""))
        fallback_path = str(
            RESULTS_DIR / f"prediccion_{fecha_str}_factork_{args.factor_k}.csv")
        predict_main(
            datasets=datasets,
            modelos=modelos,
            fecha_ini=args.fecha_ini,
            fecha_fin=args.fecha_fin,
            factor_k=args.factor_k,
            engine=engine_escritura,
            fallback_path=fallback_path,
        )

    LOGGER.info("Pipeline completado")


if __name__ == "__main__":
    main()