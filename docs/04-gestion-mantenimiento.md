# 04 · Gestión y mantenimiento

## Operativa diaria

- El servicio **`predictor`** recalcula al arrancar y cada día a `HORA_EJECUCION`
  (por defecto 03:00). Predice la ventana `[hoy, hoy+PRED_DIAS]`.
- Resultados en `silver_tourism.predictions` y `prediction_historic`; copia de
  seguridad en `backend/results/*.csv` si falla la escritura en BBDD.

## Logs

```bash
docker compose logs -f predictor     # cálculo del modelo
docker compose logs -f api           # API
docker compose logs -f frontend      # nginx
```

Kubernetes: `kubectl logs deploy/api`, `kubectl logs job/<cronjob-run>`.

## Recálculo manual

```bash
docker compose exec predictor \
  python /app/src/main.py --fecha-ini 2026-07-29 --fecha-fin 2026-08-05 --factor-k 0.563
```

## Parámetros habituales (`.env`)

| Variable | Efecto |
|---|---|
| `PRED_DIAS` | horizonte de predicción (días) |
| `HORA_EJECUCION` | hora del recálculo diario |
| `FACTOR_K` | factor de calibración sensor→personas |

## Ajuste del modelo

- **Factor K**: calibra el nº de personas frente al conteo del sensor. Ajustar en
  `config/model.json` (`factor_k`) o por `.env` (`FACTOR_K`).
- **Prophet**: `changepoint_prior_scale`, `seasonality_*` en `config/model.json`.
- **Ventana de entrenamiento**: `train_ini_global` y `ventana_max_anos`.

## Copias de seguridad

- **BBDD**: `pg_dump` del esquema de salida (y de entrada si es propio del módulo).
- **Configuración**: versionar `config/` (marca, zonas, conectores, modelo).

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| El frontal dice "No hay datos" | el job aún no ha corrido o no hay entrada | ver logs de `predictor`; revisar conectores/CSV |
| `predictor` usa CSV en vez de BBDD | tablas de entrada inexistentes o credenciales | revisar `connectors.json` y `.env` |
| Error Prophet `stan_backend` | versión de `cmdstanpy` incompatible | mantener `cmdstanpy==1.2.4` (ya fijado) |
| `/api/*` 502 en el frontal | `api` no levantó | `docker compose logs api` |
| Colores/nombre no cambian | `branding.json` no montado | revisar volumen `./config/branding` |

## Actualización del módulo

```bash
git pull
docker compose up -d --build
```

Las personalizaciones (`config/`, `.env`) se conservan por estar fuera de las imágenes.
