# 01 · Despliegue

## A) Docker Compose (recomendado para on-premise / demo)

Requisitos: Docker + Docker Compose.

```bash
cp .env.example .env         # edita credenciales de BBDD y territorio
docker compose up -d --build
```

Servicios que levanta:

| Servicio | Rol | Puerto |
|---|---|---|
| `postgres` | BBDD (crea el esquema de salida) | interno 5432 |
| `predictor` | job diario: entrena y predice | — |
| `api` | API REST de resultados | interno 8000 |
| `frontend` | frontal Angular (nginx, proxy `/api`) | `${FRONTEND_PORT}` → 80 |

Comprobaciones:

```bash
curl http://localhost:8080/api/health          # {"status":"ok",...}
docker compose logs -f predictor                # ver el cálculo del modelo
```

### Usar una BBDD PostgreSQL existente

Quita el servicio `postgres` del compose (o ignóralo) y define en `.env`:

```
DB_HOST=mi-host-postgres
DB_PORT=5432
PGSSLMODE=require
```

Asegúrate de crear el esquema de salida (ver `db/init/01_schema.sql`).

---

## B) Kubernetes

Piezas equivalentes (ver **[02-arquitectura.md](02-arquitectura.md)**):

- **Deployment `api`** (imagen backend, `command: uvicorn api:app`) + **Service** `api:8000`.
- **CronJob `predictor`** (imagen backend, entrypoint del job) — recomendado en k8s
  usar un `CronJob` diario en vez del bucle `sleep` del entrypoint.
- **Deployment `frontend`** (imagen frontend/nginx) + **Service** + **Ingress**.
- **ConfigMap** con `config/` (model.json, zones.json, connectors.json, branding) montado en
  `/config` del backend y en `/usr/share/nginx/html/assets/branding` del frontend.
- **Secret** con las credenciales de BBDD (`.env`).
- **PostgreSQL**: `StatefulSet` propio o servicio gestionado.

Construir y publicar imágenes:

```bash
docker build -t <registry>/modelo-predictivo-backend:1.0.0 ./backend
docker build -t <registry>/modelo-predictivo-frontend:1.0.0 ./frontend
docker push <registry>/modelo-predictivo-backend:1.0.0
docker push <registry>/modelo-predictivo-frontend:1.0.0
```

> En k8s, sustituye el bucle diario del `entrypoint.sh` por un `CronJob`
> (`schedule: "0 3 * * *"`) que ejecute `python main.py --fecha-ini <hoy>
> --fecha-fin <hoy+PRED_DIAS>`.
