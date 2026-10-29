# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════
#  DASHBOARD MIMD · versión simple
#  Python + MySQL + Streamlit + Plotly
#  Orden: filtros → cantidad de datos (barras por rango) → porcentajes (pastel)
#         → tiempo de ejecución → conclusiones → tabla de la base de datos
#  Ejecutar:  streamlit run dashboard.py
# ════════════════════════════════════════════════════════════════════════════

import os
import threading
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ── Clasificadores (criterio educativo, no diagnóstico médico) ──────────────
def clasificar_pam(v):
    """< 70 Hipotensión · 70–105 Normal · > 105 Hipertensión."""
    return np.select([v < 70, v <= 105], ["Hipotensión", "Normal"], "Hipertensión")

def clasificar_pp(v):
    """< 40 Estrecha · 40–60 Normal · > 60 Amplia."""
    return np.select([v < 40, v <= 60], ["Estrecha", "Normal"], "Amplia")

def clasificar_ic(v):
    """< 0.7 Normal · 0.7–0.9 Vigilancia · ≥ 0.9 Crítico."""
    return np.select([v < 0.7, v < 0.9], ["Normal", "Vigilancia"], "Crítico")

# Colores por categoría (alto contraste: azul = bajo, verde = normal,
# ámbar = vigilancia, rojo = alto/crítico)
COLORES = {
    "Normal": "#16A34A", "Vigilancia": "#D97706",
    "Hipotensión": "#0284C7", "Estrecha": "#0284C7",
    "Hipertensión": "#DC2626", "Amplia": "#DC2626", "Crítico": "#991B1B",
}

# ── Configuración de la arquitectura ────────────────────────────────────────
ARQ = "MIMD"
SUBTITULO = "Análisis de presión arterial · Multiple Instruction, Multiple Data"
ACENTO = "#0F766E"        # verde azulado · color distintivo de este dashboard
ACENTO_TXT = "#115E59"    # verde azulado oscuro · títulos de gráficas y tabla
ACENTO_NOMBRE = "verde azulado"
ESPERADO_REGISTROS = 6000
BLOQUES_SIMILARES = False
HILOS_ETQ = ["Hilo PAM<br>(1–2000)", "Hilo presión de pulso<br>(2001–4000)",
             "Hilo índice de choque<br>(4001–6000)"]
SQL = """
    SELECT r.id, r.nombre, r.apellido, r.edad, r.sexo, r.PAS, r.PAD, r.FC,
           c.PAM, c.presion_pulso, c.indice_choque, c.tiempo_microsegundos
    FROM registro_paciente AS r
    INNER JOIN registro_resultados AS c ON c.id_paciente = r.id
    ORDER BY r.id
"""
METRICAS = [
    dict(col="PAM", etq="PAM", unidad="mmHg", paso=5, dec=1, dec_rango=0, bloque=1,
         ambito="pacientes 1–2000", clase=clasificar_pam, normal=(70, 105, "70–105 mmHg")),
    dict(col="presion_pulso", etq="Presión de pulso", unidad="mmHg", paso=5, dec=1, dec_rango=0,
         bloque=2, ambito="pacientes 2001–4000", clase=clasificar_pp, normal=(40, 60, "40–60 mmHg")),
    dict(col="indice_choque", etq="Índice de choque", unidad="FC/PAS", paso=0.05, dec=3, dec_rango=2,
         bloque=3, ambito="pacientes 4001–6000", clase=clasificar_ic, normal=(0, 0.7, "< 0.7")),
]
COLS_TABLA = ["id", "nombre", "apellido", "edad", "sexo", "PAS", "PAD", "FC",
              "PAM", "presion_pulso", "indice_choque", "tiempo_microsegundos"]
TABLA_NOTA = ("Cada indicador solo se calculó en su bloque; fuera de él la base guarda 0 "
              "(no calculado).")
CONCLUSION_ARQ = ("cada hilo ejecutó una instrucción distinta sobre un bloque distinto de pacientes "
                  "(PAM en 1–2000, presión de pulso en 2001–4000, índice de choque en 4001–6000); "
                  "por eso cada indicador existe solo en su bloque.")

# ── Configuración de la página (primer comando de Streamlit) ────────────────
st.set_page_config(page_title=f"Dashboard {ARQ}", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Jost:wght@400;500;600&display=swap');
html, body, .stApp { background:#FFFFFF !important; color:#1F2937; font-family:'Jost','Segoe UI',sans-serif; }
#MainMenu, footer { display:none; }
div.block-container { max-width:1280px; padding-top:4.2rem; padding-bottom:3rem; }
h1, h2, h3 { font-family:'Playfair Display',Georgia,serif !important; color:#111827 !important; }
.titulo { font-family:'Playfair Display',Georgia,serif; font-size:2.4rem; font-weight:700; color:#111827; margin:0; }
.titulo span { color:#0F766E; }
.subtitulo { color:#4B5563; margin:.2rem 0 .8rem; font-size:1.02rem; }
.chip { display:inline-block; padding:4px 14px; border-radius:999px; font-size:.78rem; font-weight:600; letter-spacing:.04em; }
.chip-live { background:#DCFCE7; color:#15803D; border:1px solid #86EFAC; }
.chip-demo { background:#FEF3C7; color:#B45309; border:1px solid #FCD34D; }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:1rem 0 .4rem; }
.kpi { background:#fff; border:1px solid #E2E8F0; border-radius:14px; padding:14px 18px; box-shadow:0 6px 18px -12px rgba(15,23,42,.28); }
.kpi span { display:block; font-size:.78rem; color:#4B5563; text-transform:uppercase; letter-spacing:.08em; }
.kpi b { font-family:'Playfair Display',Georgia,serif; font-size:1.9rem; color:#0F766E; }
.sec { display:flex; gap:14px; align-items:center; margin:2.4rem 0 .4rem; padding-top:1.2rem; border-top:1px solid #E2E8F0; }
.sec .num { flex:none; width:38px; height:38px; border-radius:50%; background:#0F766E; color:#fff; font-weight:600; display:flex; align-items:center; justify-content:center; }
.sec h2 { margin:0; font-size:1.55rem; }
.sec p { margin:0; color:#4B5563; font-size:.95rem; }
table.esp { width:100%; border-collapse:collapse; background:#fff; border:1px solid #E2E8F0; border-radius:12px; overflow:hidden; }
table.esp th { background:#F1F5F9; color:#115E59; text-align:left; padding:10px 14px; font-size:.85rem; }
table.esp td { padding:10px 14px; border-top:1px solid #F1F5F9; font-size:.95rem; }
.ok { color:#15803D; font-weight:600; } .mal { color:#B91C1C; font-weight:600; }
section[data-testid="stSidebar"] { background:#F8FAFC; border-right:1px solid #E2E8F0; }
/* ── Tema claro FIJO: aunque el navegador esté en modo oscuro, los textos
   del panel de filtros siempre se ven oscuros y legibles (nunca invisibles) ── */
html { color-scheme: light; }
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] span,
section[data-testid="stSidebar"] [data-testid="stRadio"] p,
section[data-testid="stSidebar"] [data-testid="stRadio"] label,
section[data-testid="stSidebar"] [data-testid="stRadio"] label p,
section[data-testid="stSidebar"] .stMarkdown h3,
section[data-testid="stSidebar"] .stMarkdown p { color:#1F2937 !important; font-weight:600 !important; }
/* Botón "Refrescar datos": verde azulado del dashboard, texto blanco, sin bordes negros */
section[data-testid="stSidebar"] button {
    background:#0F766E !important; color:#FFFFFF !important;
    border:1px solid #0F766E !important; font-weight:600 !important; box-shadow:none !important; }
section[data-testid="stSidebar"] button:hover { filter:brightness(1.12); }
/* Círculos de radio con fondo blanco (jamás rellenos negros) */
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label > div:first-child { background:#FFFFFF !important; }
</style>
""", unsafe_allow_html=True)


def seccion(num, titulo, sub):
    st.markdown(
        f'<div class="sec"><div class="num">{num}</div>'
        f'<div><h2>{titulo}</h2><p>{sub}</p></div></div>',
        unsafe_allow_html=True)

def miles(n):
    return f"{int(n):,}".replace(",", " ")

def tema(fig, titulo, altura=440):
    """Estilo común de las gráficas (fondo transparente, tipografía clara)."""
    fig.update_layout(
        height=altura,
        title=dict(text=titulo, x=0.01, font=dict(size=20, color=ACENTO_TXT,
                   family="Playfair Display, Georgia, serif")),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#334155", family="Jost, Segoe UI, sans-serif", size=14),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", title_text=""),
        margin=dict(l=20, r=20, t=70, b=20),
    )
    fig.update_xaxes(gridcolor="rgba(148,163,184,.30)", linecolor="rgba(148,163,184,.60)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,.30)", linecolor="rgba(148,163,184,.60)")
    return fig


# ════════════════════════════════════════════════════════════════════════════
# CARGA DE DATOS · MySQL real; si no responde, modo demo con datos.csv
# ════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def cargar_datos_mysql():
    """Lee las tablas reales que llena main.py (JOIN pacientes + resultados)."""
    from conexion import conectar_mysql
    conexion = conectar_mysql()
    try:
        cursor = conexion.cursor(dictionary=True)
        try:
            cursor.execute(SQL)
            return pd.DataFrame(cursor.fetchall())
        finally:
            cursor.close()
    finally:
        conexion.close()

def cargar_datos_demo():
    """Modo demo: replica main.py — cada hilo ejecuta una instrucción DISTINTA
    sobre un bloque DISTINTO de pacientes."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos.csv")
    pacientes = pd.read_csv(ruta, encoding="utf-8-sig")
    n = len(pacientes)
    pas, pad, fc = pacientes["PAS"].tolist(), pacientes["PAD"].tolist(), pacientes["FC"].tolist()
    pam, pp, ic = [0.0] * n, [0.0] * n, [0.0] * n
    tiempos = [0.0, 0.0, 0.0]
    b1, b2 = min(2000, n), min(4000, n)

    def hilo_pam():
        t0 = time.perf_counter_ns()
        for i in range(0, b1):
            pam[i] = (pas[i] + 2 * pad[i]) / 3
        tiempos[0] = (time.perf_counter_ns() - t0) / 1_000_000.0

    def hilo_pp():
        t0 = time.perf_counter_ns()
        for i in range(b1, b2):
            pp[i] = pas[i] - pad[i]
        tiempos[1] = (time.perf_counter_ns() - t0) / 1_000_000.0

    def hilo_ic():
        t0 = time.perf_counter_ns()
        for i in range(b2, n):
            ic[i] = fc[i] / pas[i]
        tiempos[2] = (time.perf_counter_ns() - t0) / 1_000_000.0

    t0 = time.perf_counter_ns()
    hilos = [threading.Thread(target=f) for f in (hilo_pam, hilo_pp, hilo_ic)]
    for h in hilos: h.start()
    for h in hilos: h.join()
    total = (time.perf_counter_ns() - t0) / 1_000_000.0
    pacientes["PAM"], pacientes["presion_pulso"], pacientes["indice_choque"] = pam, pp, ic
    pacientes["tiempo_microsegundos"] = total
    return pacientes, tiempos

@st.cache_data(ttl=60, show_spinner=False)
def tiempos_otras_arquitecturas():
    """Intenta leer el tiempo guardado en las bases de las 3 arquitecturas
    (proyecto_simd, proyecto_misd, proyecto_mimd) con las mismas credenciales."""
    resultado = {}
    try:
        from conexion import conectar_mysql
        conexion = conectar_mysql()
        try:
            for arq in ("SIMD", "MISD", "MIMD"):
                try:
                    conexion.database = f"proyecto_{arq.lower()}"
                    cur = conexion.cursor()
                    cur.execute("SELECT tiempo_microsegundos FROM registro_resultados LIMIT 1")
                    fila = cur.fetchone()
                    cur.close()
                    if fila and fila[0] is not None:
                        resultado[arq] = float(fila[0])
                except Exception:
                    pass
        finally:
            conexion.close()
    except Exception:
        pass
    return resultado

MODO_DEMO = False
tiempos_hilos = None
try:
    datos = cargar_datos_mysql()
    if datos.empty:
        raise ValueError("MySQL sin filas: ejecuta main.py para poblar la base")
except Exception:
    datos, tiempos_hilos = cargar_datos_demo()
    MODO_DEMO = True

for col in ["edad", "PAS", "PAD", "FC", "tiempo_microsegundos"] + [m["col"] for m in METRICAS]:
    if col in datos.columns:
        datos[col] = pd.to_numeric(datos[col], errors="coerce")
datos["id"] = datos["id"].astype(int)
datos["bloque"] = (datos["id"] - 1) // 2000 + 1      # hilo/bloque: 1–2000, 2001–4000, 4001–6000
TIEMPO_TOTAL = float(datos["tiempo_microsegundos"].dropna().iloc[-1]) if len(datos) else 0.0


def solo_ambito(df, m):
    """Filas donde la métrica existe (en MIMD, solo su bloque)."""
    return df if m["bloque"] is None else df[df["bloque"] == m["bloque"]]


# ════════════════════════════════════════════════════════════════════════════
# FILTROS (obligatorios) · barra lateral
# ════════════════════════════════════════════════════════════════════════════
id_min, id_max = int(datos["id"].min()), int(datos["id"].max())
edad_min, edad_max = int(datos["edad"].min()), int(datos["edad"].max())

with st.sidebar:
    st.markdown("### Filtros")
    rango_id = st.slider("Rango de registros (ID)", id_min, id_max, (id_min, id_max))
    sexo_op = st.radio("Sexo", ["Todos", "M", "F"], horizontal=True)
    rango_edad = st.slider("Rango de edad (años)", edad_min, edad_max, (edad_min, edad_max))
    if st.button("Refrescar datos"):
        st.cache_data.clear()
        st.rerun()

mascara = datos["id"].between(*rango_id) & datos["edad"].between(*rango_edad)
if sexo_op != "Todos":
    mascara &= datos["sexo"] == sexo_op
filtrados = datos[mascara].copy()


# ════════════════════════════════════════════════════════════════════════════
# CABECERA + INDICADORES DE CANTIDAD
# ════════════════════════════════════════════════════════════════════════════
chip = ('<span class="chip chip-demo">MODO DEMO · datos.csv</span>' if MODO_DEMO
        else '<span class="chip chip-live">● MySQL EN LÍNEA</span>')
st.markdown(f'<p class="titulo">Dashboard <span>MIMD</span></p>'
            f'<p class="subtitulo">{SUBTITULO}</p>{chip}', unsafe_allow_html=True)

if filtrados.empty:
    st.warning("Ningún paciente cumple los filtros activos. Amplía el rango de edad, "
               "el sexo o los registros en el panel izquierdo.")
    st.stop()

pct_sel = 100 * len(filtrados) / len(datos)
st.markdown(
    '<div class="kpis">'
    f'<div class="kpi"><span>Registros en la base</span><b>{miles(len(datos))}</b></div>'
    f'<div class="kpi"><span>Registros en la selección</span><b>{miles(len(filtrados))}</b></div>'
    f'<div class="kpi"><span>Porcentaje seleccionado</span><b>{pct_sel:.1f} %</b></div>'
    f'<div class="kpi"><span>Tiempo de ejecución</span><b>{TIEMPO_TOTAL:.2f} ms</b></div>'
    '</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# 1 · CANTIDAD DE DATOS · barras por rango (contienen todos los datos)
# ════════════════════════════════════════════════════════════════════════════
def barras_por_rango(sub, m):
    """Cuenta pacientes por rango de la métrica; cada barra = un rango."""
    x = sub[m["col"]].astype(float)
    paso, d = m["paso"], m["dec_rango"]
    k = np.floor(x / paso + 1e-9).astype(int)
    conteo = k.value_counts().sort_index()
    conteo = conteo.reindex(range(conteo.index.min(), conteo.index.max() + 1), fill_value=0)
    ini = conteo.index.to_numpy() * paso
    tabla = pd.DataFrame({
        "Rango": [f"{a:.{d}f}–{a + paso:.{d}f}" for a in ini],
        "Pacientes": conteo.to_numpy(),
        "Categoría": m["clase"](ini + paso / 2),
    })
    fig = px.bar(tabla, x="Rango", y="Pacientes", color="Categoría", text="Pacientes",
                 color_discrete_map=COLORES, category_orders={"Rango": list(tabla["Rango"])})
    fig.update_traces(textposition="outside", cliponaxis=False,
                      marker_line_color="rgba(255,255,255,.8)", marker_line_width=.6)
    fig.update_layout(bargap=.08)
    fig.update_xaxes(title_text=f"{m['etq']} ({m['unidad']}) · rangos de {paso:g}", type="category")
    fig.update_yaxes(title_text="cantidad de pacientes")
    return tema(fig, f"{m['etq']}: pacientes por rango · n = {miles(len(sub))}")

seccion(1, "Cantidad de datos por rango",
        "Cada barra cuenta cuántos pacientes caen en un rango; el color indica la categoría")
for m in METRICAS:
    sub = solo_ambito(filtrados, m)
    if m["ambito"]:
        st.caption(f"{m['etq']} · {m['ambito']}")
    if sub.empty:
        st.info(f"Sin pacientes de {m['ambito'] or 'la selección'} con los filtros actuales.")
        continue
    st.plotly_chart(barras_por_rango(sub, m), config={"displayModeBar": False})


# ════════════════════════════════════════════════════════════════════════════
# 2 · PORCENTAJES · gráfico de pastel
# ════════════════════════════════════════════════════════════════════════════
def pastel(sub, m):
    cats = pd.Series(m["clase"](sub[m["col"]].to_numpy(dtype=float))).value_counts()
    cats = cats[cats > 0]
    fig = go.Figure(go.Pie(
        labels=list(cats.index), values=list(cats.values), hole=.45, sort=False,
        marker=dict(colors=[COLORES[c] for c in cats.index], line=dict(color="#FFFFFF", width=2)),
        textinfo="percent", textposition="outside", textfont=dict(size=17, color="#1F2937"),
        hovertemplate="%{label}: %{value} pacientes (%{percent})<extra></extra>"))
    tema(fig, m["etq"], altura=400)
    fig.update_layout(margin=dict(l=70, r=70, t=70, b=20))
    return fig, cats

seccion(2, "Porcentajes por categoría",
        "Qué proporción de los pacientes cae en cada categoría clínica")
columnas = st.columns(len(METRICAS))
for col_st, m in zip(columnas, METRICAS):
    with col_st:
        sub = solo_ambito(filtrados, m)
        if sub.empty:
            st.info("Sin datos en la selección.")
            continue
        fig, cats = pastel(sub, m)
        st.plotly_chart(fig, config={"displayModeBar": False})
        st.caption(" · ".join(f"{c}: {miles(v)}" for c, v in cats.items()))


# ════════════════════════════════════════════════════════════════════════════
# 3 · TIEMPO DE EJECUCIÓN
# ════════════════════════════════════════════════════════════════════════════
seccion(3, "Tiempo de ejecución",
        "Milisegundos que tardó el procesamiento con hilos de main.py")
if MODO_DEMO and tiempos_hilos:
    filas_t = [(etq, t) for etq, t in zip(HILOS_ETQ, tiempos_hilos)] + [(f"Total {ARQ}", TIEMPO_TOTAL)]
    colores_t = ["#94A3B8"] * len(tiempos_hilos) + [ACENTO]
else:
    otras = tiempos_otras_arquitecturas()
    otras[ARQ] = TIEMPO_TOTAL
    orden = [a for a in ("SIMD", "MISD", "MIMD") if a in otras]
    filas_t = [(a, otras[a]) for a in orden]
    colores_t = [ACENTO if a == ARQ else "#94A3B8" for a in orden]
tabla_t = pd.DataFrame(filas_t, columns=["Proceso", "ms"])
fig_t = go.Figure(go.Bar(
    x=tabla_t["Proceso"], y=tabla_t["ms"], marker_color=colores_t,
    text=[f"{v:.2f} ms" for v in tabla_t["ms"]], textposition="outside", cliponaxis=False))
fig_t.update_yaxes(title_text="milisegundos (ms)", rangemode="tozero")
fig_t.update_layout(bargap=.45)
fig_t.update_xaxes(tickangle=0)
st.plotly_chart(tema(fig_t, "Tiempo de ejecución", altura=420), config={"displayModeBar": False})
st.caption("En la base se guarda en la columna tiempo_microsegundos, pero main.py "
           "escribe el valor en milisegundos. En " + ACENTO_NOMBRE + ", la arquitectura " + ARQ + ".")


# ════════════════════════════════════════════════════════════════════════════
# 4 · CONCLUSIONES frente a los datos esperados
# ════════════════════════════════════════════════════════════════════════════
seccion(4, "Conclusiones",
        "Resultados obtenidos frente a lo que se espera de esta arquitectura")

revisiones = [("Registros procesados (base completa)", miles(ESPERADO_REGISTROS),
               miles(len(datos)), len(datos) == ESPERADO_REGISTROS)]
for m in METRICAS:
    n_esp = ESPERADO_REGISTROS // 3 if m["bloque"] else ESPERADO_REGISTROS
    n_obt = int((solo_ambito(datos, m)[m["col"]] > 0).sum())
    revisiones.append((f"{m['etq']} calculada" + (f" ({m['ambito']})" if m["ambito"] else ""),
                       miles(n_esp), miles(n_obt), n_obt == n_esp))
    sub = solo_ambito(filtrados, m)
    if not sub.empty:
        media = float(sub[m["col"]].mean())
        lo, hi, texto = m["normal"]
        revisiones.append((f"{m['etq']}: media en rango normal", texto,
                           f"{media:.{m['dec']}f} {m['unidad']}", lo <= media <= hi))
revisiones.append(("Tiempo de ejecución registrado", "> 0 ms", f"{TIEMPO_TOTAL:.2f} ms", TIEMPO_TOTAL > 0))
if BLOQUES_SIMILARES:
    m0 = METRICAS[0]
    por_bloque = filtrados.groupby("bloque")[m0["col"]].mean()
    if len(por_bloque) > 1:
        dif = float(por_bloque.max() - por_bloque.min())
        revisiones.append(("Medias de los 3 bloques similares", "diferencia ≤ 2 mmHg",
                           f"diferencia {dif:.2f} mmHg", dif <= 2))

filas_html = "".join(
    f"<tr><td>{c}</td><td>{e}</td><td>{o}</td>"
    f"<td class='{'ok' if ok else 'mal'}'>{'✔ Cumple' if ok else '✖ Revisar'}</td></tr>"
    for c, e, o, ok in revisiones)
st.markdown(
    "<table class='esp'><tr><th>Criterio</th><th>Esperado</th><th>Obtenido</th><th>Estado</th></tr>"
    + filas_html + "</table>", unsafe_allow_html=True)

st.markdown("&nbsp;")
with st.container(border=True):
    st.markdown("**Lectura de los resultados** (con los filtros actuales)")
    for m in METRICAS:
        sub = solo_ambito(filtrados, m)
        if sub.empty:
            continue
        cats = pd.Series(m["clase"](sub[m["col"]].to_numpy(dtype=float))).value_counts()
        top, pct = cats.index[0], 100 * cats.iloc[0] / cats.sum()
        st.markdown(f"- **{m['etq']}**: media {sub[m['col']].mean():.{m['dec']}f} {m['unidad']}; "
                    f"la categoría predominante es «{top}» con {pct:.1f} % de los pacientes.")
    st.markdown(f"- **Tiempo**: el procesamiento con hilos tardó {TIEMPO_TOTAL:.2f} ms en total.")
    st.markdown(f"- **Arquitectura**: {CONCLUSION_ARQ}")


# ════════════════════════════════════════════════════════════════════════════
# 5 · TABLA DE LA BASE DE DATOS (al final)
# ════════════════════════════════════════════════════════════════════════════
seccion(5, "Tabla de la base de datos",
        ("Registros del modo demo (datos.csv): mismas columnas que MySQL" if MODO_DEMO
         else "Registros almacenados en MySQL (registro_paciente + registro_resultados)"))
st.dataframe(filtrados[COLS_TABLA], height=460, hide_index=True)
st.caption(f"{miles(len(filtrados))} de {miles(len(datos))} registros según los filtros. "
           + TABLA_NOTA)