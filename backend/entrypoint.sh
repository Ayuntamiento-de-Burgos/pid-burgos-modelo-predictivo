#!/bin/sh
# Módulo Sinergia · Modelo Predictivo — Job diario de entrenamiento+predicción.
# Cada día (a HORA_EJECUCION) entrena con el histórico y predice la ventana
# [hoy, hoy+PRED_DIAS], escribiendo en las tablas de salida (o CSV si no hay BBDD).
set -u

cd /app/src

PRED_DIAS="${PRED_DIAS:-7}"
HORA_EJECUCION="${HORA_EJECUCION:-03:00}"
FACTOR_K="${FACTOR_K:-0.563}"

run() {
    INI="$(date +%F)"
    FIN="$(date -d "+${PRED_DIAS} days" +%F)"
    echo "[modelo] $(date '+%F %T') — prediccion ${INI} -> ${FIN} (factor-k=${FACTOR_K})"
    python main.py --fecha-ini "${INI}" --fecha-fin "${FIN}" --factor-k "${FACTOR_K}" \
        || echo "[modelo] WARN: la ejecucion terminó con error (ver log arriba)"
}

# Ejecución inicial al arrancar
run

# Bucle diario
while true; do
    NOW="$(date +%s)"
    NEXT="$(date -d "tomorrow ${HORA_EJECUCION}" +%s)"
    SLEEP=$((NEXT - NOW))
    echo "[modelo] durmiendo ${SLEEP}s hasta $(date -d "@${NEXT}" '+%F %T')"
    sleep "${SLEEP}"
    run
done
