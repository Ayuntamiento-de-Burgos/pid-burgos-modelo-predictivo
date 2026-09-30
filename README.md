# Módulo Sinergia · Modelo Predictivo de Afluencia

Módulo **autónomo y personalizable** de predicción de afluencia turística por
zonas, basado en **Prophet**. Nace del CU#48 de la PID de Burgos y se ha
**generalizado** para que cualquier destino (p. ej. Ayuntamiento de Las Rozas)
lo despliegue en su entorno, apunte a **sus propios conectores** y lo
**personalice** (marca, zonas, textos) sin tocar código.

Se entrega como repositorio + `docker-compose` (o manifiestos Kubernetes) para
un despliegue con un solo comando.

---

## Qué incluye

| Componente | Descripción |
|---|---|
| **backend** | Pipeline Prophet (`preprocess → train → predict`) + **API REST** (FastAPI) + **job diario**. |
| **frontend** | Frontal **Angular** con dashboard de histórico y predicción por zona; marca en runtime. |
| **config/** | Toda la personalización (editable sin recompilar): zonas, conectores, modelo, marca, datos maestros. |
| **db/** | Inicialización del esquema de salida en PostgreSQL. |
| **docs/** | Despliegue, arquitectura, personalización y mantenimiento. |

## Arranque rápido (demo, datos de ejemplo de Burgos)

```bash
cp .env.example .env         # ajusta credenciales de BBDD
docker compose up -d --build
```

- Frontal: <http://localhost:8080>
- API: `http://localhost:8080/api/health`

El `predictor` calcula al arrancar (con los CSV de ejemplo si aún no hay
conectores) y cada día a `HORA_EJECUCION`. El frontal muestra el resultado.

## Estructura

```
pid-modulo-modelo-predictivo/
├── docker-compose.yml         # postgres + predictor + api + frontend
├── .env.example               # credenciales, territorio, parámetros del job
├── config/                    # ← PERSONALIZACIÓN (sin recompilar)
│   ├── model.json             #   parámetros Prophet, ciudad, festivos, factor K
│   ├── zones.json             #   zonas del destino ↔ sensores de afluencia
│   ├── connectors.json        #   esquemas/tablas de entrada y salida (tus conectores)
│   ├── master-data.seed.csv   #   datos maestros (códigos territoriales + zonas)
│   └── branding/              #   branding.json, logo.png, login-background.jpg, favicon.ico
├── backend/                   # modelo + API (Python)
│   ├── src/                   #   config.py, database.py, preprocess/train/predict, api.py
│   └── data/                  #   CSVs de ejemplo (fallback si no hay BBDD)
├── frontend/                  # Angular + nginx
└── docs/                      # 01-despliegue · 02-arquitectura · 03-personalizacion · 04-gestion
```

## Personalizar para tu destino (resumen)

1. **Marca** → `config/branding/branding.json` + `logo.png`, `login-background.jpg`, `favicon.ico`.
2. **Zonas** → `config/zones.json` (tus zonas y el mapeo a tus sensores de afluencia).
3. **Conectores** → `config/connectors.json` (esquema y tablas donde tus conectores dejan los datos).
4. **Territorio** → `APP_*` en `.env` + `config/master-data.seed.csv` (mismos códigos).
5. **Modelo** → `config/model.json` (festivos locales, coords del municipio, factor K).

Detalle completo en **[docs/03-personalizacion.md](docs/03-personalizacion.md)**.

> Los **conectores de datos de entrada** (afluencia, meteo, eventos) los
> implementa **cada destino para sus zonas**. Este módulo solo consume las
> tablas que indiques en `connectors.json`; incluye datos de ejemplo para poder
> arrancar y ver el frontal antes de tener conectores propios.
