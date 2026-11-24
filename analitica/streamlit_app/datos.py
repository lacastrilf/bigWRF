"""Acceso a datos: Athena (real) o datos sinteticos (modo demo, solo para probar la interfaz)."""

import os
import time
import zlib

import numpy as np
import pandas as pd

REGION = os.environ.get("AWS_REGION", "us-east-1")
WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "p2-derecho")


def ejecutar_athena(sql):
    import boto3

    athena = boto3.client("athena", region_name=REGION)
    qid = athena.start_query_execution(QueryString=sql, WorkGroup=WORKGROUP)["QueryExecutionId"]
    while True:
        estado = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if estado["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if estado["State"] != "SUCCEEDED":
        raise RuntimeError(estado.get("StateChangeReason", estado["State"]))

    filas = []
    for pagina in athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for fila in pagina["ResultSet"]["Rows"]:
            filas.append([c.get("VarCharValue") for c in fila["Data"]])
    if not filas:
        return pd.DataFrame()
    df = pd.DataFrame(filas[1:], columns=filas[0])  # la primera fila son los encabezados
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass
    return df


# ---------------------------------------------------------------- modo demo
# Datos inventados con la misma forma que las consultas reales. No son resultados del proyecto.
_CIUDADES = ["Chicago", "Gary", "Fort Wayne", "Milwaukee", "Indianapolis", "Des Moines",
             "Cedar Rapids", "Detroit", "South Bend", "Rockford"]


def demo(clave, p):
    rng = np.random.default_rng(zlib.crc32(clave.encode()))
    esq = p["esquemas"][0] if p.get("esquemas") else "thompson"
    horas = pd.date_range(p["t0"], p["t1"], freq="h") if "t0" in p else pd.DatetimeIndex([])
    if clave == "ciudades":
        return pd.DataFrame({"name": _CIUDADES})
    if clave == "ciudades_geo":
        return pd.DataFrame({"name": ["Chicago", "Fort Wayne", "Indianapolis", "Milwaukee"],
                             "lat": [41.88, 41.08, 39.77, 43.04], "lon": [-87.63, -85.14, -86.16, -87.91]})
    if clave == "esquemas":
        return pd.DataFrame({"esquema": ["thompson"]})
    if clave == "p1":
        return pd.DataFrame([{"esquema": esq, "hora": horas[len(horas) // 2], "viento_max_ms": 31.7,
                              "lat": 41.1, "lon": -85.1, "ciudad_cercana": "Fort Wayne",
                              "state": "IN", "distancia_km": 13.0}])
    if clave == "p1_horas":
        return pd.DataFrame({"esquema": esq, "hora": horas, "viento_max_ms": rng.uniform(8, 34, len(horas)).round(2)})
    if clave in ("p2", "p4_ciudades"):
        c = p["ciudades"] or _CIUDADES
        v = np.sort(rng.uniform(5, 34, len(c)))[::-1]
        col = "viento_max_ms" if clave == "p2" else "lluvia_mm"
        d = pd.DataFrame({"esquema": esq, "ciudad": c, col: v.round(1), "posicion": range(1, len(c) + 1)})
        if clave == "p2":
            d["hora_pico"] = horas[len(horas) // 2]
        return d.head(p["top"])
    if clave == "p3":
        a = np.clip(rng.normal(300, 200, len(horas)).cumsum() % 2500, 0, None)
        return pd.DataFrame({"esquema": esq, "hora": horas, "celdas_severas": (a / 9).astype(int),
                             "area_km2": a.round(0)})
    if clave == "p4_max":
        return pd.DataFrame([{"esquema": esq, "lluvia_max_mm": 98.4, "lat": 41.4, "lon": -86.2}])
    if clave == "p5":
        c = p["ciudades"] or _CIUDADES
        return pd.DataFrame({"esquema": esq, "ciudad": c, "hora": horas[0],
                             "t_antes_c": 30.0, "t_despues_c": 24.0,
                             "caida_c": np.sort(rng.uniform(1, 9, len(c)))[::-1].round(2)}).head(p["top"])
    if clave == "p6_global":
        return pd.DataFrame([{"esquema": esq, "n": 120, "rmse_viento_ms": 3.4, "sesgo_viento_ms": 0.8,
                              "rmse_lluvia_mm": 2.1, "rmse_temp_c": 2.7}])
    if clave == "p6_estacion":
        est = ["KORD", "KMDW", "KGYY", "KFWA", "KIND", "KMKE"]
        return pd.DataFrame({"esquema": esq, "station_id": est, "n": 20,
                             "rmse_viento_ms": rng.uniform(2, 6, 6).round(2),
                             "sesgo_viento_ms": rng.uniform(-2, 2, 6).round(2),
                             "rmse_lluvia_mm": rng.uniform(0, 4, 6).round(2),
                             "rmse_temp_c": rng.uniform(1, 4, 6).round(2)})
    if clave == "p7":
        return pd.DataFrame([{"esquema": esq, "reportes_spc": 80, "con_celda_severa_cercana": 52,
                              "porcentaje": 65.0}])
    if clave == "mapa":
        n = min(p["limite"], 800)
        lat0, lat1, lon0, lon1 = p["bbox"]
        return pd.DataFrame({"lat": rng.uniform(lat0, lat1, n), "lon": rng.uniform(lon0, lon1, n),
                             "valor": rng.uniform(p["vmin"], p["vmax"], n)})
    if clave == "serie":
        filas = [(h, c, 20 + 10 * np.sin(i / 3 + k)) for k, c in enumerate(p["ciudades"])
                 for i, h in enumerate(horas)]
        return pd.DataFrame(filas, columns=["hora", "ciudad", "valor"])
    raise KeyError(clave)
