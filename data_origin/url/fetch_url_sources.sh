#!/usr/bin/env bash
# Descarga las dos fuentes URL a una carpeta local (por defecto ./out).
# Uso: ./fetch_url_sources.sh [carpeta_salida]
set -euo pipefail
cd "$(dirname "$0")"; source urls.env
OUT="${1:-out}"; mkdir -p "$OUT/asos" "$OUT/spc"

# --- ASOS: una peticion con todas las estaciones (parametro station repetido) ---
ST=""; for s in $ASOS_STATIONS; do ST+="&station=$s"; done
Y1=${EVENT_DATE:0:4}; M1=$((10#${EVENT_DATE:5:2})); D1=$((10#${EVENT_DATE:8:2}))
Y2=${ASOS_END_DATE:0:4}; M2=$((10#${ASOS_END_DATE:5:2})); D2=$((10#${ASOS_END_DATE:8:2}))
curl -fsS "$ASOS_BASE?data=all&year1=$Y1&month1=$M1&day1=$D1&year2=$Y2&month2=$M2&day2=$D2&tz=Etc/UTC&format=onlycomma&latlon=yes&missing=M&trace=T&direct=no&report_type=3&report_type=4$ST" \
  -o "$OUT/asos/asos.csv"

# --- SPC: reportes de viento del dia (nombre = aammdd_rpts_wind.csv) ---
YMD="${EVENT_DATE:2:2}${EVENT_DATE:5:2}${EVENT_DATE:8:2}"
curl -fsS "$SPC_BASE/${YMD}_rpts_wind.csv" -o "$OUT/spc/wind_reports.csv"

wc -l "$OUT"/asos/asos.csv "$OUT"/spc/wind_reports.csv
