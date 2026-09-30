-- Módulo Sinergia · Modelo Predictivo — inicialización de BBDD (demo).
-- Crea el esquema de SALIDA donde el job escribe predicciones e histórico.
-- Las tablas se crean solas en la primera ejecución del job (to_sql), pero
-- el esquema debe existir de antemano.
--
-- Las tablas de ENTRADA (afluencia, meteo, eventos) NO se crean aquí: en el
-- demo el job cae al CSV de ejemplo (backend/data). En un destino real, esas
-- tablas las alimentan los conectores propios del destino (ver connectors.json).

CREATE SCHEMA IF NOT EXISTS silver_tourism;

-- (Opcional) tablas de salida vacías, por si se quiere consultarlas antes del
-- primer run. El job hará TRUNCATE+append sobre ellas.
CREATE TABLE IF NOT EXISTS silver_tourism.predictions (
    timestamp          timestamp,
    zone_num           integer,
    zone_name          text,
    visitor_prediction double precision
);

CREATE TABLE IF NOT EXISTS silver_tourism.prediction_historic (
    timestamp  timestamp,
    zone_num   integer,
    zone_name  text,
    visitors   double precision
);
