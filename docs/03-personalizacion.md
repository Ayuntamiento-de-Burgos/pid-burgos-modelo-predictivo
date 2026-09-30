# 03 · Personalización

Toda la personalización vive en `config/` y en `.env`. **No hay que recompilar**:
en compose se montan como volúmenes; en k8s como ConfigMap/Secret.

## 1. Marca (`config/branding/`)

- **`branding.json`** — nombre del destino, colores, textos, rutas de assets y enlaces.
  El frontal lo lee en runtime (`/api/branding`) y aplica colores (variables CSS),
  título y favicon.
- **`logo.png`** — logotipo (cabecera; y login si se habilita).
- **`login-background.jpg`** — imagen de fondo de acceso.
- **`favicon.ico`** — icono de pestaña.

Los tres assets incluidos son *placeholders*: sustitúyelos por los del destino
(mismos nombres). En compose se sirven desde `config/branding/` sin reconstruir.

```json
{
  "destino": { "nombre": "Ayuntamiento de Las Rozas", "descripcion": "..." },
  "colores": { "primary": "#005aa7", "primary_dark": "#00335f", "accent": "#e6f0fa" },
  "assets":  { "logo": "assets/branding/logo.png", "favicon": "assets/branding/favicon.ico" },
  "textos":  { "footer": "..." }
}
```

## 2. Zonas y sensores (`config/zones.json`)

Define las zonas del destino y su mapeo a los sensores de afluencia:

- `modo: "unico"` → solo sensor `principal`.
- `modo: "principal_respaldo"` → si falta el principal, usa `respaldo × factor_respaldo`.
- `modo: "suma"` → `principal + respaldo` con `factor_sin_principal` / `factor_sin_respaldo`.
- `sensor_coords` → coordenadas `[lat, lon]` de cada sensor (para asignar eventos por radio).

## 3. Conectores (`config/connectors.json`)

Indica **dónde deja los datos cada conector del destino**:

| Clave | Qué es |
|---|---|
| `input_schema` / `output_schema` | esquemas de entrada y salida en PostgreSQL |
| `tables.afluencia_visitas` / `afluencia_zonas` | tablas de tu conector de afluencia (obligatorio) |
| `tables.meteo` + `meteo.estacion` | tabla y estación meteo (opcional) |
| `tables.eventos_local` / `eventos_regional` | fuentes de eventos (opcional; `null` = omitir) |
| `read_enabled` / `write_enabled` | activar lectura/escritura en BBDD |

> Si aún no tienes conectores, deja `read_enabled: true`: el modelo intentará
> leer de BBDD y, si no existen las tablas, caerá a los CSV de ejemplo.

## 4. Territorio (`.env` + `config/master-data.seed.csv`)

Los códigos de `.env` **deben coincidir** con los del CSV de datos maestros.

| Destino | `APP_AUTONOMOUS_COMMUNITY` | `APP_PROVINCE` | `APP_MUNICIPALITY` |
|---|---|---|---|
| Burgos (demo incluido) | `ES-CYL` | `ES-BU` | `ES-BU-BU` |
| **Las Rozas de Madrid** | **`ES-MD`** | **`ES-M`** | **`ES-MD-ROZ`** |

`master-data.seed.csv` (una fila por zona):

```csv
autonomous_community,province,municipality,zone_num,zone_name,zone_label,lat,lon
ES-MD,ES-M,ES-MD-ROZ,1,centro,Centro,40.4926,-3.8740
...
```

## 5. Modelo (`config/model.json`)

- `factor_k` — calibración sensor→personas.
- `ciudad.lat` / `ciudad.lon` — centro del municipio (asignación de eventos por radio).
- `festivos_locales` — festivos del municipio (`"YYYY-MM-DD": "nombre"`).
- `prophet_params`, `regressors`, `train_ini_global`, `ventana_max_anos`.

## Checklist "nuevo destino"

- [ ] `branding.json` + assets del destino.
- [ ] `zones.json` con las zonas y sensores reales.
- [ ] `connectors.json` apuntando a las tablas de tus conectores.
- [ ] `master-data.seed.csv` + `APP_*` en `.env` con los códigos territoriales.
- [ ] `model.json`: festivos, coordenadas y factor K del destino.
- [ ] Conectores de entrada implementados y poblando el esquema de entrada.
