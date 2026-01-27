# -*- coding: utf-8 -*-
"""
Painel Dash para visualizar as figuras geradas pelo ECMWF
+ mapa de SOBREPOSIÇÃO (camada previsão GeoJSON + pontos de unidades UPA/UBS/UBSI).

Arquivos esperados no MESMO repo (Render):
- PNGs na raiz:
    ecmwf_prec_YYYY-MM-DD.png
    ecmwf_tmin_YYYY-MM-DD.png
    ecmwf_tmax_YYYY-MM-DD.png
    ecmwf_tmed_YYYY-MM-DD.png
    ecmwf_prec_acumulada_YYYY-MM-DD_a_YYYY-MM-DD.png

- Unidades (Point GeoJSON) na raiz:
    upa.geojson
    ubs.geojson
    ubsi.geojson
  (pode estar com letras maiúsculas/minúsculas variadas; o app resolve)

- Camadas previsão (GeoJSON MultiPolygon por classe) em:
    camadas_geojson/  OU na raiz
      prec_YYYY-MM-DD.geojson
      tmin_YYYY-MM-DD.geojson
      tmax_YYYY-MM-DD.geojson
      tmed_YYYY-MM-DD.geojson
      prec_acum_YYYY-MM-DD_a_YYYY-MM-DD.geojson
"""

from pathlib import Path
import base64
import json
from datetime import datetime
import re

from dash import Dash, html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

# ----------------- CONFIGURAÇÕES ----------------- #
BASE_DIR = Path(__file__).parent
IMG_DIR = BASE_DIR

CAMADAS_DIR = BASE_DIR / "camadas_geojson"
CAMADAS_FALLBACK_DIRS = [CAMADAS_DIR, BASE_DIR]  # procura primeiro na pasta, depois na raiz

# Recorte padrão (igual às figuras)
# (lon_min, lon_max, lat_min, lat_max)
EXTENT = (-90, -30, -60, 15)

# ----------------- VARIÁVEIS DISPONÍVEIS (PREVISÃO PNG) ----------------- #
VAR_OPCOES = {
    "prec": {"label": "Precipitação diária (mm)", "prefix": "ecmwf_prec_", "usa_data": True},
    "tmin": {"label": "Temperatura mínima diária (°C)", "prefix": "ecmwf_tmin_", "usa_data": True},
    "tmax": {"label": "Temperatura máxima diária (°C)", "prefix": "ecmwf_tmax_", "usa_data": True},
    "tmed": {"label": "Temperatura média diária (°C)", "prefix": "ecmwf_tmed_", "usa_data": True},
    "prec_acum": {"label": "Precipitação acumulada no período (mm)", "prefix": "ecmwf_prec_acumulada_", "usa_data": False},
}

# ----------------- HELPERS (PNG) ----------------- #
def listar_datas_disponiveis():
    datas = set()
    for img_path in IMG_DIR.glob("ecmwf_prec_*.png"):
        stem = img_path.stem
        parte_data = stem.replace("ecmwf_prec_", "", 1)
        try:
            datetime.strptime(parte_data, "%Y-%m-%d")
            datas.add(parte_data)
        except ValueError:
            continue
    return sorted(datas)

def formatar_label_br(data_iso: str) -> str:
    dt = datetime.strptime(data_iso, "%Y-%m-%d")
    return dt.strftime("%d/%m/%Y")

def carregar_imagem_base64(var_key: str, data_iso: str | None) -> str:
    info = VAR_OPCOES[var_key]
    prefix = info["prefix"]

    if var_key == "prec_acum":
        candidates = sorted(IMG_DIR.glob(f"{prefix}*.png"))
        if not candidates:
            print(f"⚠️ Nenhuma imagem acumulada encontrada com padrão {prefix}*.png")
            return ""
        img_path = candidates[-1]
    else:
        if data_iso is None:
            return ""
        img_path = IMG_DIR / f"{prefix}{data_iso}.png"

    if not img_path.exists():
        print(f"⚠️ PNG não encontrado: {img_path.name}")
        return ""

    with open(img_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"

def construir_figura_estatica(src: str, titulo: str) -> go.Figure:
    fig = go.Figure()
    if src:
        fig.add_layout_image(
            dict(
                source=src,
                xref="x", yref="y",
                x=0, y=1,
                sizex=1, sizey=1,
                sizing="stretch",
                layer="below",
            )
        )
    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 1], scaleanchor="x")
    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=45, b=0),
        dragmode="pan",
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig

def construir_animacao(var_key: str, datas_iso: list[str], titulo: str) -> go.Figure:
    if not datas_iso:
        return construir_figura_estatica("", "Sem dados para animar")

    src0 = carregar_imagem_base64(var_key, datas_iso[0])
    fig = go.Figure()

    if src0:
        fig.add_layout_image(
            dict(
                source=src0,
                xref="x", yref="y",
                x=0, y=1,
                sizex=1, sizey=1,
                sizing="stretch",
                layer="below",
            )
        )

    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 1], scaleanchor="x")

    frames = []
    for d in datas_iso:
        src = carregar_imagem_base64(var_key, d)
        frames.append(
            go.Frame(
                name=d,
                layout=dict(images=[dict(
                    source=src, xref="x", yref="y",
                    x=0, y=1, sizex=1, sizey=1,
                    sizing="stretch", layer="below"
                )]),
            )
        )
    fig.frames = frames

    slider_steps = [
        dict(
            method="animate",
            args=[[f.name], {"mode": "immediate", "frame": {"duration": 500, "redraw": True}, "transition": {"duration": 0}}],
            label=formatar_label_br(f.name),
        )
        for f in frames
    ]

    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=45, b=40),
        dragmode="pan",
        sliders=[dict(
            active=0, steps=slider_steps,
            x=0.1, y=0, len=0.9,
            pad={"t": 30, "b": 10},
            currentvalue={"prefix": "Data: "},
            transition={"duration": 0},
        )],
        updatemenus=[dict(
            type="buttons", showactive=False,
            x=0.0, y=1.05,
            xanchor="left", yanchor="top",
            buttons=[dict(
                label="▶ Play", method="animate",
                args=[None, {"frame": {"duration": 500, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0}}],
            )],
        )],
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig

# ----------------- HELPERS (RESOLVER ARQUIVOS NA RAIZ, CASE-INSENSITIVE) ----------------- #
def resolver_arquivo_geojson_unidades(key: str) -> Path | None:
    """
    Resolve upa/ubs/ubsi.geojson na raiz, ignorando maiúsculas/minúsculas.
    Ex.: UBS.geojson vai ser encontrado no Render (Linux).
    """
    target = f"{key}.geojson".lower()
    for p in BASE_DIR.glob("*.geojson"):
        if p.name.lower() == target:
            return p
    return None

# ----------------- HELPERS (UNIDADES) ----------------- #
def carregar_geojson_points(caminho: Path | None, camada: str):
    if (caminho is None) or (not caminho.exists()):
        print(f"⚠️ GeoJSON não encontrado (unidades): {camada}")
        return [], [], []

    with open(caminho, "r", encoding="utf-8") as f:
        gj = json.load(f)

    lats, lons, custom = [], [], []
    feats = gj.get("features", [])

    # ✅ ÚNICA CORREÇÃO: aceitar Point/MultiPoint (maiúsculo/minúsculo) e converter coords para float
    def _to_float(x):
        try:
            return float(x)
        except Exception:
            return None

    for ft in feats:
        geom = ft.get("geometry", {}) or {}
        props = ft.get("properties", {}) or {}

        gtype = (geom.get("type") or "").strip().lower()

        # Pega campos de atributos 1x (vale para Point e MultiPoint)
        nome = (
            props.get("nm_fantasia") or props.get("NM_FANTASIA")
            or props.get("nome_da_es") or props.get("NOME_DA_ES")
            or props.get("nome") or props.get("NOME") or ""
        )
        cnes = props.get("cd_cnes") or props.get("CD_CNES") or props.get("cnes") or props.get("CNES") or ""
        cd_mun = props.get("cd_mun") or props.get("CD_MUN") or props.get("cod_mun") or props.get("COD_MUN") or ""

        dsei = props.get("dsei") or props.get("DSEI") or ""
        polo = props.get("polo_base") or props.get("POLO_BASE") or ""
        cod_polo = props.get("cod_polo") or props.get("COD_POLO") or ""

        if gtype == "point":
            coords = geom.get("coordinates", None)
            if not coords or len(coords) < 2:
                continue

            lon = _to_float(coords[0])
            lat = _to_float(coords[1])
            if lon is None or lat is None:
                continue

            lats.append(lat)
            lons.append(lon)
            custom.append([camada.upper(), nome, cnes, cd_mun, dsei, polo, cod_polo, lat, lon])

        elif gtype == "multipoint":
            coords_list = geom.get("coordinates", None)
            if not coords_list:
                continue

            for coords in coords_list:
                if not coords or len(coords) < 2:
                    continue
                lon = _to_float(coords[0])
                lat = _to_float(coords[1])
                if lon is None or lat is None:
                    continue

                lats.append(lat)
                lons.append(lon)
                custom.append([camada.upper(), nome, cnes, cd_mun, dsei, polo, cod_polo, lat, lon])

        else:
            # Ignora outros tipos (LineString/Polygon etc.)
            continue

    return lats, lons, custom

# ----------------- HELPERS (CAMADAS PREVISÃO) ----------------- #
def _latest_file_in_dirs(pattern: str) -> Path | None:
    cands = []
    for d in CAMADAS_FALLBACK_DIRS:
        if d.exists():
            cands += list(d.glob(pattern))
    cands = sorted(cands)
    return cands[-1] if cands else None

# ✅ ALTERAÇÃO (ÚNICA): resolver camadas da previsão ignorando maiúsc/minúsc no Render
def _resolver_arquivo_case_insensitive(nome_arquivo: str) -> Path | None:
    alvo = nome_arquivo.lower()
    for d in CAMADAS_FALLBACK_DIRS:
        if not d.exists():
            continue
        for p in d.glob("*.geojson"):
            if p.name.lower() == alvo:
                return p
    return None

def caminho_camadas_previsao_exata(var_key: str, data_iso: str | None) -> Path | None:
    """
    IMPORTANTE: usa data EXATA.
    - prec/tmin/tmax/tmed: var_YYYY-MM-DD.geojson
    - prec_acum: prec_acum_YYYY-MM-DD_a_YYYY-MM-DD.geojson (mais recente)
    """
    if var_key == "prec_acum":
        return _latest_file_in_dirs("prec_acum_*.geojson")

    if not data_iso:
        return None

    # ✅ resolve ignorando maiúsc/minúsc (Render)
    return _resolver_arquivo_case_insensitive(f"{var_key}_{data_iso}.geojson")

def carregar_geojson_poligonos_por_classe(path_geojson: Path | None):
    if (path_geojson is None) or (not path_geojson.exists()):
        return []
    with open(path_geojson, "r", encoding="utf-8") as f:
        gj = json.load(f)
    feats = gj.get("features", []) or []

    def _ord(ft):
        try:
            return int((ft.get("properties") or {}).get("ordem", 0))
        except Exception:
            return 0

    return sorted(feats, key=_ord)

# ----------------- MAPA OVERLAY ----------------- #
def construir_mapa_sobreposicao(var_key: str, data_iso: str | None, camada_unidade: str, mostrar_previsao: bool, mostrar_unidades: bool) -> go.Figure:
    fig = go.Figure()

    lon_min, lon_max, lat_min, lat_max = EXTENT
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2
    zoom = 2.0

    # --- PREVISÃO (POLÍGONOS) ---
    if mostrar_previsao:
        p = caminho_camadas_previsao_exata(var_key, data_iso)
        feats = carregar_geojson_poligonos_por_classe(p)

        # Se não achou o arquivo da data, não plota nada (e o título deixa claro)
        if not feats:
            if var_key == "prec_acum":
                titulo_prev = "Camada previsão: Precipitação acumulada (arquivo não encontrado)"
            else:
                titulo_prev = f"Camada previsão: {VAR_OPCOES[var_key]['label']} – {formatar_label_br(data_iso)} (arquivo não encontrado)" if data_iso else "Camada previsão: (arquivo não encontrado)"
        else:
            for i, ft in enumerate(feats):
                props = ft.get("properties", {}) or {}
                label = props.get("label", f"classe {i}")
                hex_color = props.get("hex", "#999999")
                ordem = int(props.get("ordem", i))

                # FIX Plotly: id bate com locations
                ft2 = dict(ft)
                ft2["id"] = f"classe_{ordem}"
                gj_one = {"type": "FeatureCollection", "features": [ft2]}

                fig.add_trace(
                    go.Choroplethmapbox(
                        geojson=gj_one,
                        featureidkey="id",
                        locations=[ft2["id"]],
                        z=[1],
                        colorscale=[[0, hex_color], [1, hex_color]],
                        showscale=False,
                        marker_opacity=0.60,
                        marker_line_width=0,
                        marker_line_color="rgba(0,0,0,0)",  # ✅ borda totalmente transparente
                        name=label,               # ✅ legenda por intervalo
                        legendgroup="previsao",
                        legendrank=ordem,
                        hovertemplate=f"<b>{label}</b><extra></extra>",
                        showlegend=True,
                    )
                )

            if var_key == "prec_acum":
                titulo_prev = "Camada previsão: Precipitação acumulada"
            else:
                titulo_prev = f"Camada previsão: {VAR_OPCOES[var_key]['label']} – {formatar_label_br(data_iso)}" if data_iso else f"Camada previsão: {VAR_OPCOES[var_key]['label']}"
    else:
        titulo_prev = "Camada previsão: (desligada)"

    # --- UNIDADES (PONTOS) ---
    if mostrar_unidades:
        arq = resolver_arquivo_geojson_unidades(camada_unidade)
        lats, lons, custom = carregar_geojson_points(arq, camada_unidade)

        if lats and lons:
            fig.add_trace(
                go.Scattermapbox(
                    lat=lats,
                    lon=lons,
                    mode="markers",
                    marker=dict(size=7, opacity=0.9, color="black"),  # ✅ todos os pontos pretos
                    customdata=custom,
                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "Camada: %{customdata[0]}<br>"
                        "CNES: %{customdata[2]}<br>"
                        "CD_MUN: %{customdata[3]}<br>"
                        "DSEI: %{customdata[4]}<br>"
                        "Polo: %{customdata[5]} (%{customdata[6]})<br>"
                        "Lat/Lon: %{customdata[7]:.3f}, %{customdata[8]:.3f}"
                        "<extra></extra>"
                    ),
                    name=f"Unidades – {camada_unidade.upper()}",
                    legendgroup="unidades",
                    showlegend=True,
                )
            )

    titulo = f"Sobreposição – {titulo_prev} + {('Unidades: ' + camada_unidade.upper()) if mostrar_unidades else 'Unidades: (desligadas)'}"

    # ✅ força redraw do GeoJSON quando muda data/variável/camada/toggles (sem perder o zoom, pq uirevision fica fixo)
    datarevision_key = f"{var_key}|{data_iso}|{camada_unidade}|{int(mostrar_previsao)}|{int(mostrar_unidades)}"

    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=45, b=0),
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=2.0,
            minzoom=0.8,   # 👈 permite afastar mais (ajuste fino)
            maxzoom=6.5,   # 👈 evita zoom exagerado
            bounds=dict(
                west=lon_min, east=lon_max,
                south=lat_min, north=lat_max
            ),
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top", y=0.98,
            xanchor="left", x=1.01,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="rgba(0,0,0,0.15)",
            borderwidth=1,
            traceorder="normal",
            font=dict(size=11),
        ),
        uirevision="overlay_lock",
        datarevision=datarevision_key,  # ✅ chave que muda e obriga redesenho
    )
    return fig

# ----------------- PREPARA LISTA DE DATAS ----------------- #
DATAS = listar_datas_disponiveis()
if not DATAS:
    raise RuntimeError(
        f"Nenhuma data diária encontrada em {IMG_DIR}. "
        f"Certifique-se de que existam arquivos ecmwf_prec_YYYY-MM-DD.png."
    )
DATA_DEFAULT = DATAS[-1]

# ----------------- APP DASH ----------------- #
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
app.title = "Previsão ECMWF - Painel de Mapas"

app.layout = dbc.Container(
    [
        html.H2(
            "Painel de Monitoramento Meteorológico - CGCLIMA/SSCLIMA",
            className="mt-3 mb-2",
            style={"textAlign": "center"},
        ),
        html.Div(
            "Visualização diária (figuras) + sobreposição (camadas GeoJSON + UPA/UBS/UBSI).",
            className="mb-3",
            style={"textAlign": "center"},
        ),

        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H5("Campos de seleção", className="mb-3"),

                        html.Label("Variável (previsão):", className="fw-bold"),
                        dcc.RadioItems(
                            id="radio-var",
                            options=[{"label": v["label"], "value": k} for k, v in VAR_OPCOES.items()],
                            value="prec",
                            labelStyle={"display": "block"},
                            className="mb-3",
                        ),

                        html.Label("Data da previsão:", className="fw-bold"),
                        dcc.Dropdown(
                            id="dropdown-data",
                            options=[{"label": formatar_label_br(d), "value": d} for d in DATAS],
                            value=DATA_DEFAULT,
                            clearable=False,
                            className="mb-3",
                        ),

                        html.Label("Modo de visualização (previsão PNG):", className="fw-bold"),
                        dcc.RadioItems(
                            id="radio-modo",
                            options=[
                                {"label": "Mapa diário", "value": "dia"},
                                {"label": "Animação (todos os dias)", "value": "anim"},
                            ],
                            value="dia",
                            labelStyle={"display": "block"},
                            className="mb-2",
                        ),
                        html.Small(
                            "Obs: Animação não se aplica à precipitação acumulada; nesse caso, o PNG é estático.",
                            className="text-muted",
                        ),

                        html.Hr(),

                        html.Label("Unidades de Saúde (para sobreposição):", className="fw-bold"),
                        dcc.Dropdown(
                            id="dropdown-unidades",
                            options=[
                                {"label": "UPA", "value": "upa"},
                                {"label": "UBS", "value": "ubs"},
                                {"label": "UBSI", "value": "ubsi"},
                            ],
                            value="upa",
                            clearable=False,
                            className="mb-2",
                        ),

                        html.Hr(),

                        html.Label("Mapa de SOBREPOSIÇÃO (embaixo):", className="fw-bold"),
                        dcc.Checklist(
                            id="check-overlay",
                            options=[
                                {"label": "Mostrar previsão (GeoJSON)", "value": "prev"},
                                {"label": "Mostrar unidades (pontos)", "value": "uni"},
                            ],
                            value=["prev", "uni"],
                            labelStyle={"display": "block"},
                            className="mb-2",
                        ),
                        html.Small(
                            "Previsão usa GeoJSON em /camadas_geojson (ou na raiz).",
                            className="text-muted",
                        ),
                    ],
                    md=3, lg=3, xl=3,
                ),

                # ✅ só a FIGURA à direita (sem mapa de unidades ao lado)
                dbc.Col(
                    [
                        dcc.Graph(
                            id="graph-mapa",
                            style={"height": "75vh"},
                            config={"scrollZoom": True, "displayModeBar": False},
                        )
                    ],
                    md=9, lg=9, xl=9,
                ),
            ],
            className="mb-2",
        ),

        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(
                            id="graph-overlay",
                            style={"height": "65vh"},
                            config={"scrollZoom": True, "displayModeBar": False},
                        )
                    ]
                )
            ],
            className="mb-3",
        ),

        html.Hr(),
        html.Footer(
            "Fonte: ECMWF Open Data – Processamento local (Pedro / Dash) • Unidades: GeoJSON (UPA/UBS/UBSI) • Camadas: GeoJSON por classes",
            className="text-muted mt-1 mb-2",
            style={"fontSize": "0.85rem"},
        ),
    ],
    fluid=True,
)

# ----------------- CALLBACKS ----------------- #
@app.callback(
    Output("graph-mapa", "figure"),
    Input("dropdown-data", "value"),
    Input("radio-var", "value"),
    Input("radio-modo", "value"),
)
def atualizar_mapa_previsao(data_iso, var_key, modo):
    if var_key is None:
        return go.Figure()

    info = VAR_OPCOES[var_key]

    if var_key == "prec_acum":
        src = carregar_imagem_base64("prec_acum", None)
        return construir_figura_estatica(src, info["label"])

    if modo == "dia":
        if data_iso is None:
            return go.Figure()
        titulo = f"{info['label']} – {formatar_label_br(data_iso)}"
        src = carregar_imagem_base64(var_key, data_iso)
        return construir_figura_estatica(src, titulo)

    titulo = f"{info['label']} – (animação)"
    return construir_animacao(var_key, DATAS, titulo)

@app.callback(
    Output("graph-overlay", "figure"),
    Input("dropdown-data", "value"),
    Input("radio-var", "value"),
    Input("dropdown-unidades", "value"),
    Input("check-overlay", "value"),
)
def atualizar_overlay(data_iso, var_key, camada_unidade, check_values):
    check_values = check_values or []
    mostrar_previsao = "prev" in check_values
    mostrar_unidades = "uni" in check_values

    return construir_mapa_sobreposicao(
        var_key=var_key,
        data_iso=data_iso,
        camada_unidade=camada_unidade or "upa",
        mostrar_previsao=mostrar_previsao,
        mostrar_unidades=mostrar_unidades,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)











