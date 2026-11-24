"""Lambda de ingesta de la fuente URL -> S3 (zona raw).

Descarga dos CSV publicos y los guarda SIN transformar:
  raw/url/asos/fecha=AAAA-MM-DD/asos.csv           (IEM, observaciones de estaciones ASOS)
  raw/url/spc/fecha=AAAA-MM-DD/wind_reports.csv    (SPC, reportes de viento)

Variables de entorno: BUCKET, EVENT_DATE (AAAA-MM-DD), ASOS_STATIONS (codigos FAA separados por espacio).
El evento puede traer {"event_date": "AAAA-MM-DD"} para usar otro dia.
"""
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta


ASOS_BASE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
SPC_BASE = "https://www.spc.noaa.gov/climo/reports"


def asos_url(event_date: date, stations: list) -> str:
    end = event_date + timedelta(days=2)  # la fecha final de IEM es exclusiva
    params = [
        ("data", "all"),
        ("year1", event_date.year), ("month1", event_date.month), ("day1", event_date.day),
        ("year2", end.year), ("month2", end.month), ("day2", end.day),
        ("tz", "Etc/UTC"), ("format", "onlycomma"), ("latlon", "yes"),
        ("missing", "M"), ("trace", "T"), ("direct", "no"),
        ("report_type", 3), ("report_type", 4),
    ] + [("station", s) for s in stations]
    return ASOS_BASE + "?" + urllib.parse.urlencode(params)


def spc_url(event_date: date) -> str:
    return f"{SPC_BASE}/{event_date:%y%m%d}_rpts_wind.csv"


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "proyecto2-ingesta"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def lambda_handler(event, context):
    import boto3 

    bucket = os.environ["BUCKET"]
    day = (event or {}).get("event_date") or os.environ["EVENT_DATE"]
    event_date = date.fromisoformat(day)
    stations = os.environ["ASOS_STATIONS"].split()

    s3 = boto3.client("s3")
    salida = {}
    for nombre, url, key in [
        ("asos", asos_url(event_date, stations), f"raw/url/asos/fecha={day}/asos.csv"),
        ("spc", spc_url(event_date), f"raw/url/spc/fecha={day}/wind_reports.csv"),
    ]:
        datos = download(url)
        s3.put_object(Bucket=bucket, Key=key, Body=datos, ContentType="text/csv")
        salida[nombre] = {"key": key, "bytes": len(datos), "filas": datos.count(b"\n")}
        print(nombre, salida[nombre])
    return salida
