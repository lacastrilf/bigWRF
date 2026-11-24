"""Streamlit: preguntas del caso Derecho (WRF Thompson) con filtros propios.

Ejecutar:   streamlit run app.py
Sin datos:  DERECHO_DEMO=1 streamlit run app.py   (datos inventados, solo para ver la interfaz)
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import pydeck as pdk
import streamlit as st

import datos
import queries as Q

st.set_page_config(page_title="Derecho WRF", page_icon="🌪️", layout="wide")

# ----------------------------------------------------------------- catalogo de preguntas
PREGUNTAS = {
    "P1": ("¿Cuál fue el viento máximo a 10 m, a qué hora y cerca de qué ciudad?", "Athena", "34,12 m/s",
           "ventana de tiempo, esquema"),
    "P2": ("¿Qué ciudades sufrieron los vientos más fuertes?", "Hive", "—",
           "ventana de tiempo, esquema, ciudades, máximo de filas"),
    "P3": ("¿Cuántos km² tuvieron viento severo en cada hora?", "PySpark", "—",
           "ventana de tiempo, esquema, umbral de viento"),
    "P4": ("¿Cuál fue la lluvia máxima y qué ciudades recibieron más?", "SparkSQL", "113,8 mm",
           "ventana de tiempo, esquema, ciudades, máximo de filas"),
    "P5": ("¿Cuál fue la mayor caída de temperatura en una hora?", "PySpark", "—",
           "ventana de tiempo, esquema, ciudades, máximo de filas"),
    "P6": ("¿Qué tan bien reproduce el modelo a las estaciones ASOS?", "PySpark", "—",
           "ventana de tiempo, esquema"),
    "P7": ("¿Qué porcentaje de reportes del SPC coincide con viento severo simulado?", "Athena", "—",
           "ventana de tiempo, esquema, umbral de viento, radio y viento mínimo (en esta pestaña)"),
}

st.title("🌪️ Derecho Chicago–Gary · WRF Thompson")
st.caption("Pregunta, filtros y resultado en una sola pantalla. Los datos salen de la zona "
           "trusted del data lake (tablas del catálogo Glue) vía Athena.")

# ----------------------------------------------------------------- barra lateral
with st.sidebar:
    st.header("Filtros globales")
    demo_activo = st.toggle("Modo demo (datos inventados)", value=os.environ.get("DERECHO_DEMO") == "1",
                            help="Solo para ver la interfaz sin conexión a AWS. No son resultados reales.")

    @st.cache_data(ttl=3600, show_spinner=False)
    def _lista(sql, clave, demo_flag):
        df = datos.demo(clave, {}) if demo_flag else datos.ejecutar_athena(sql)
        return df.iloc[:, 0].tolist()

    try:
        todas_ciudades = _lista(Q.SQL_CIUDADES, "ciudades", demo_activo)
        todos_esquemas = _lista(Q.SQL_ESQUEMAS, "esquemas", demo_activo)
    except Exception as e:  # sin credenciales / sin tablas todavía
        st.error(f"No se pudo leer el catálogo de Athena: {e}")
        st.info("Activa el modo demo para ver la interfaz.")
        st.stop()

    inicio_dia = datetime(2026, 8, 11)
    t0, t1 = st.slider("Ventana de tiempo (UTC)", min_value=inicio_dia,
                       max_value=inicio_dia + timedelta(hours=47),
                       value=(inicio_dia + timedelta(hours=12), inicio_dia + timedelta(hours=20)),
                       step=timedelta(hours=1), format="DD/MM HH:mm")
    esquemas = st.multiselect("Esquema de microfísica", todos_esquemas, default=todos_esquemas)
    ciudades = st.multiselect("Ciudades (vacío = todas)", todas_ciudades)
    umbral = st.number_input("Umbral de viento severo (m/s)", 5.0, 80.0, 25.7, 0.1,
                             help="25,7 m/s ≈ 50 kt, el umbral del NWS para viento severo.")
    top = st.number_input("Máximo de filas en rankings", 1, 100, 10)

if not esquemas:
    st.warning("Elige al menos un esquema.")
    st.stop()

fechas = sorted({(t0 + timedelta(days=d)).strftime("%Y-%m-%d") for d in range((t1.date() - t0.date()).days + 1)})
P = dict(t0=t0, t1=t1, fechas=fechas, esquemas=esquemas, ciudades=ciudades, umbral=umbral, top=top,
         viento_min_spc=0.0, radio_grados=0.1)


@st.cache_data(ttl=600, show_spinner="Consultando Athena…")
def correr(clave, sql, demo_flag, p_repr):
    # p_repr solo sirve para que la caché distinga filtros distintos
    return datos.demo(clave, PARAMS_ACTUALES) if demo_flag else datos.ejecutar_athena(sql)


PARAMS_ACTUALES = P


def consulta(clave, funcion, p=None):
    p = p or P
    global PARAMS_ACTUALES
    PARAMS_ACTUALES = p
    sql = funcion(p) if not demo_activo else ""
    try:
        return correr(clave, sql, demo_activo, repr(sorted(p.items(), key=lambda kv: kv[0]))), sql
    except Exception as e:
        st.error(f"La consulta falló: {e}")
        return None, sql


def encabezado(codigo):
    texto, motor, control, filtros = PREGUNTAS[codigo]
    st.subheader(f"{codigo}. {texto}")
    st.info(f"**Filtros que cambian esta pestaña:** {filtros}. Los demás de la barra lateral no le afectan.")
    st.caption(f"En el proyecto se resuelve con **{motor}** (carpeta analitica/). Aquí se recalcula en "
               f"Athena para poder variar los filtros. Valor de control del reporte: {control}.")


def ver_sql(sql):
    if sql:
        with st.expander("Ver la consulta SQL"):
            st.code(sql, language="sql")


if demo_activo:
    st.warning("MODO DEMO: los números son inventados, solo sirven para ver cómo se ve la interfaz.")

def mapa(df, valor=None, radio_m=1500, marcas=None, zoom=6, etiqueta="valor"):
    """Mapa pydeck: puntos con tamano minimo visible, coloreados por valor; marcas = ciudades."""
    capas = []
    if df is not None and not df.empty:
        d = df.copy()
        if "name" not in d:
            d["name"] = etiqueta
        if valor and d[valor].max() > d[valor].min():
            r = (d[valor] - d[valor].min()) / (d[valor].max() - d[valor].min())
        else:
            r = pd.Series(1.0, index=d.index)
        d["_r"] = (255 * r).astype(int)
        d["_g"] = (200 * (1 - r)).astype(int)
        d["_v"] = d[valor].round(2).astype(str) if valor else ""
        capas.append(pdk.Layer("ScatterplotLayer", d, get_position=["lon", "lat"],
                               get_fill_color=["_r", "_g", 40, 200], get_radius=radio_m,
                               radius_min_pixels=5, pickable=True))
    if marcas is not None and not marcas.empty:
        capas.append(pdk.Layer("ScatterplotLayer", marcas, get_position=["lon", "lat"],
                               get_fill_color=[30, 60, 120, 220], get_radius=3000,
                               radius_min_pixels=6, pickable=True))
    base = df if (df is not None and not df.empty) else marcas
    vista = pdk.ViewState(latitude=float(base["lat"].mean()), longitude=float(base["lon"].mean()),
                          zoom=zoom)
    st.pydeck_chart(pdk.Deck(layers=capas, initial_view_state=vista,
                             tooltip={"text": f"{{name}}\n{etiqueta}: {{_v}}"}))


@st.cache_data(ttl=3600, show_spinner=False)
def _ciudades_geo(demo_flag):
    return (datos.demo("ciudades_geo", {}) if demo_flag else datos.ejecutar_athena(Q.SQL_CIUDADES_GEO))


st.markdown(f"**Filtros activos:** {t0:%d/%m %H:%M} → {t1:%d/%m %H:%M} UTC · esquemas: {', '.join(esquemas)} · "
            f"ciudades: {', '.join(ciudades) if ciudades else 'todas'} · umbral: {umbral} m/s · filas: {top}")

tabs = st.tabs(list(PREGUNTAS) + ["🔎 Explorador libre"])

# ----------------------------------------------------------------- P1
with tabs[0]:
    encabezado("P1")
    df, sql = consulta("p1", Q.p1)
    horas_df, sql_h = consulta("p1_horas", Q.p1_horas)
    if df is not None and not df.empty:
        f = df.iloc[0]
        a, b, c = st.columns(3)
        a.metric("Viento máximo", f"{f.viento_max_ms:.2f} m/s")
        b.metric("Hora (UTC)", str(f.hora))
        c.metric("Ciudad cercana", f"{f.ciudad_cercana}, {f.state}", f"{f.distancia_km} km")
        pico = df.assign(name="Pico de viento", valor=f.viento_max_ms)
        mapa(pico, valor="valor", radio_m=6000, marcas=_ciudades_geo(demo_activo), zoom=6,
             etiqueta="m/s")
        st.caption("Rojo: pico de viento. Azul: ciudades del RDS (pasa el mouse para ver el nombre).")
        st.dataframe(df, hide_index=True, width='stretch')
    if horas_df is not None and not horas_df.empty:
        st.markdown("**Viento máximo del dominio por hora** (cambia con la ventana de tiempo)")
        st.bar_chart(horas_df.pivot(index="hora", columns="esquema", values="viento_max_ms"))
    ver_sql(sql + "\n-- por hora --\n" + sql_h if sql else "")

# ----------------------------------------------------------------- P2
with tabs[1]:
    encabezado("P2")
    df, sql = consulta("p2", Q.p2)
    if df is not None and not df.empty:
        st.bar_chart(df.set_index("ciudad")["viento_max_ms"])
        st.dataframe(df, hide_index=True, width='stretch')
    ver_sql(sql)

# ----------------------------------------------------------------- P3
with tabs[2]:
    encabezado("P3")
    df, sql = consulta("p3", Q.p3)
    if df is not None and not df.empty:
        pico = df.loc[df.area_km2.idxmax()]
        st.metric("Mayor área severa", f"{pico.area_km2:,.0f} km²", f"{pico.hora}")
        st.line_chart(df.pivot(index="hora", columns="esquema", values="area_km2"))
        st.dataframe(df, hide_index=True, width='stretch')
        st.caption("Área = celdas con viento ≥ umbral × 9 km² (celda de 3 km del dominio d01).")
    ver_sql(sql)

# ----------------------------------------------------------------- P4
with tabs[3]:
    encabezado("P4")
    mx, sql1 = consulta("p4_max", Q.p4_max)
    ci, sql2 = consulta("p4_ciudades", Q.p4_ciudades)
    if mx is not None and not mx.empty:
        st.metric("Lluvia máxima del dominio", f"{mx.iloc[0].lluvia_max_mm:.1f} mm")
        st.dataframe(mx, hide_index=True, width='stretch')
    if ci is not None and not ci.empty:
        st.bar_chart(ci.set_index("ciudad")["lluvia_mm"])
        st.dataframe(ci, hide_index=True, width='stretch')
    ver_sql(sql1 + "\n-- ciudades --\n" + sql2 if sql1 else "")

# ----------------------------------------------------------------- P5
with tabs[4]:
    encabezado("P5")
    df, sql = consulta("p5", Q.p5)
    if df is not None and not df.empty:
        f = df.iloc[0]
        st.metric("Mayor caída en 1 h", f"{f.caida_c:.2f} °C", f"{f.ciudad} · {f.hora}")
        st.bar_chart(df.set_index("ciudad")["caida_c"])
        st.dataframe(df, hide_index=True, width='stretch')
    ver_sql(sql)

# ----------------------------------------------------------------- P6
with tabs[5]:
    encabezado("P6")
    g, sql1 = consulta("p6_global", Q.p6_global)
    e, sql2 = consulta("p6_estacion", Q.p6_estacion)
    if g is not None and not g.empty:
        st.dataframe(g, hide_index=True, width='stretch')
    if e is not None and not e.empty:
        metrica = st.selectbox("Métrica por estación", [c for c in e.columns if c.startswith(("rmse", "sesgo"))])
        st.bar_chart(e.set_index("station_id")[metrica])
        st.dataframe(e, hide_index=True, width='stretch')
    st.caption("RMSE y sesgo = modelo − observación, en la celda más cercana a cada estación y hora.")
    ver_sql(sql1 + "\n-- por estación --\n" + sql2 if sql1 else "")

# ----------------------------------------------------------------- P7
with tabs[6]:
    encabezado("P7")
    c1, c2 = st.columns(2)
    P7 = dict(P, radio_grados=c1.slider("Radio de coincidencia (grados)", 0.02, 0.5, 0.1, 0.01,
                                        help="0,1° ≈ 10 km. Es una aproximación simple."),
              viento_min_spc=c2.number_input("Viento mínimo del reporte SPC (m/s)", 0.0, 80.0, 0.0, 1.0))
    df, sql = consulta("p7", Q.p7, P7)
    if df is not None and not df.empty:
        st.metric("Reportes con celda severa cercana", f"{df.iloc[0].porcentaje:.1f} %",
                  f"{int(df.iloc[0].con_celda_severa_cercana)} de {int(df.iloc[0].reportes_spc)}")
        st.dataframe(df, hide_index=True, width='stretch')
    ver_sql(sql)

# ----------------------------------------------------------------- explorador libre
with tabs[7]:
    st.subheader("Explorador libre")
    st.caption("Arma tu propio filtro: elige variable, hora, rango de valores y zona.")
    VARS = {"Viento a 10 m (m/s)": "viento_10m", "Temperatura a 2 m (°C)": "t2_c",
            "Lluvia en la hora (mm)": "lluvia_hora_mm", "Lluvia acumulada (mm)": "lluvia_acum_mm"}
    a, b = st.columns(2)
    nombre_var = a.selectbox("Variable", list(VARS))
    esquema_sel = b.selectbox("Esquema", esquemas)
    hora_sel = st.slider("Hora (UTC)", min_value=t0, max_value=t1, value=t0, step=timedelta(hours=1),
                         format="DD/MM HH:mm")
    c1, c2 = st.columns(2)
    vmin = c1.number_input("Valor mínimo", value=0.0)
    vmax = c2.number_input("Valor máximo", value=100.0)
    d1, d2, d3, d4 = st.columns(4)
    bbox = (d1.number_input("Lat mín", value=38.0), d2.number_input("Lat máx", value=45.0),
            d3.number_input("Lon mín", value=-92.0), d4.number_input("Lon máx", value=-82.0))
    limite = st.number_input("Máximo de celdas a traer", 100, 50000, 5000, 100)

    PE = dict(P, variable=VARS[nombre_var], hora=hora_sel, esquema=esquema_sel, vmin=vmin, vmax=vmax,
              bbox=bbox, limite=limite)
    mapa_df, sqlm = consulta("mapa", Q.explorador_mapa, PE)
    mapa_fn = mapa
    if mapa_df is not None:
        if mapa_df.empty:
            st.info("Ninguna celda cumple los filtros.")
        else:
            st.write(f"{len(mapa_df):,} celdas · máx {mapa_df.valor.max():.2f} · media {mapa_df.valor.mean():.2f}")
            mapa_fn(mapa_df, valor="valor", marcas=_ciudades_geo(demo_activo), zoom=6, etiqueta=nombre_var)
            st.dataframe(mapa_df.head(200), hide_index=True, width='stretch')
    ver_sql(sqlm)

    st.markdown("**Serie en el tiempo para ciudades elegidas**")
    sel = st.multiselect("Ciudades", todas_ciudades, default=todas_ciudades[:3], key="serie_ciudades")
    if sel:
        PS = dict(PE, ciudades=sel)
        serie, sqls = consulta("serie", Q.explorador_serie, PS)
        if serie is not None and not serie.empty:
            st.line_chart(serie.pivot_table(index="hora", columns="ciudad", values="valor"))
        ver_sql(sqls)
