# -*- coding: utf-8 -*-
"""
Painel Dash para visualizar as figuras geradas pelo ECMWF + mapa de SOBREPOSIÇÃO
(camadas de previsão GeoJSON + pontos de unidades UPA/UBS/UBSI).

Arquivos esperados no MESMO repo (Render):
- PNGs no mesmo diretório do app.py:
    ecmwf_prec_YYYY-MM-DD.png
    ecmwf_tmin_YYYY-MM-DD.png
    ecmwf_tmax_YYYY-MM-DD.png
    ecmwf_tmed_YYYY-MM-DD.png
    ecmwf_prec_acumulada_YYYY-MM-DD_a_YYYY-MM-DD.png

- Unidades (Point GeoJSON) no mesmo diretório do app.py:
    upa.geojson
    ubs.geojson
    ubsi.geojson

- Camadas previsão (GeoJSON MultiPolygon por classe):
    (1) em camadas_geojson/  OU
    (2) na raiz do repo

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

from dash import Dash, html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

# ----------------- CONFIGURAÇÕES ----------------- #
BASE_DIR = Path(__file__).parent
IMG_DIR = BASE_DIR
CAMADAS_DIR = BASE_DIR / "camadas_geojson"

# Recorte visual do overlay (igual às figuras)
EXTENT = (-90, -30, -60, 15)  # (lon_min, lon_max, lat_min, lat_max)

GEOJSON_FILES = {
    "upa": BASE_DIR / "upa.geojson",
    "ubs": BASE_DIR / "ubs.geojson",
    "ubsi": BASE_DIR / "ubsi.geojson",
}

# ----------------- VARIÁVEIS DISPONÍVEIS (PREVISÃO PNG) ----------------- #
VAR_OPCOES = {
    "prec": {"label": "Precipitação diária (mm)", "prefix": "ecmwf_prec_", "usa_data": True},
    "tmin": {"label": "Temperatura mínima diária (°C)", "prefix": "ecmwf_tmin_", "usa_data": True},
    "tmax": {"label": "Temperatura máxima diária (°C)", "prefix": "ecmwf_tmax_", "usa_data": True},
    "tmed": {"label": "Temperatura média diária (°C)", "prefix": "ecmwf_tmed_", "usa_data": True},
    "prec_acum": {"label": "Precipitação acumulada no período (mm)", "prefix": "ecmwf_prec_acumulada_", "usa_data": False},
}

# ----------------- HELPERS (PREVISÃO PNG) ----------------- #
def listar_datas_disponiveis():
    if not IMG_DIR.exists():
        raise FileNotFoundError(f"Pasta de imagens não encontrada: {IMG_DIR}")

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
        print(f"⚠️ PNG não encontrado: {img_path}")
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
                xref="x",
                yref="y",
                x=0,
                y=1,
                sizex=1,
                sizey=1,
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
    if len(datas_iso) == 0:
        return construir_figura_estatica("", "Sem dados para animar")

    src0 = carregar_imagem_base64(var_key, datas_iso[0])
    fig = go.Figure()

    if src0:
        fig.add_layout_image(
            dict(
                source=src0,
                xref="x",
                yref="y",
                x=0,
                y=1,
                sizex=1,
                sizey=1,
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
                layout=dict(
                    images=[
                        dict(
                            source=src,
                            xref="x",
                            yref="y",
                            x=0,
                            y=1,
                            sizex=1,
                            sizey=1,
                            sizing="stretch",
                            layer="below",
                        )
                    ],
                ),
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

    sliders = [
        dict(
            active=0,
            steps=slider_steps,
            x=0.1,
            y=0,
            len=0.9,
            pad={"t": 30, "b": 10},
            currentvalue={"prefix": "Data: "},
            transition={"duration": 0},
        )
    ]

    updatemenus = [
        dict(
            type="buttons",
            showactive=False,
            x=0.0,
            y=1.05,
            xanchor="left",
            yanchor="top",
            buttons=[
                dict(
                    label="▶ Play",
                    method="animate",
                    args=[None, {"frame": {"duration": 500, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0}}],
                )
            ],
        )
    ]

    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=45, b=40),
        dragmode="pan",
        sliders=sliders,
        updatemenus=updatemenus,
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    return fig

# ----------------- HELPERS (UNIDADES) ----------------- #
def carregar_geojson_points(caminho: Path, camada: str):
    if not caminho.exists():
        print(f"⚠️ GeoJSON não encontrado: {caminho}")
        return [], [], [], f"arquivo não encontrado: {caminho.name}"

    with open(caminho, "r", encoding="utf-8") as f:
        gj = json.load(f)

    lats, lons, custom = [], [], []
    feats = gj.get("features", [])

    for ft in feats:
        geom = ft.get("geometry", {})
        props = ft.get("properties", {}) or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates", None)
        if not coords or len(coords) < 2:
            continue

        lon, lat = coords[0], coords[1]

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

        lats.append(lat)
        lons.append(lon)
        custom.append([camada.upper(), nome, cnes, cd_mun, dsei, polo, cod_polo, lat, lon])

    return lats, lons, custom, f"{len(lats)} pontos | arquivo: {caminho.name}"

# ----------------- HELPERS (CAMADAS PREVISÃO GEOJSON) ----------------- #
def _latest_file_multi_dirs(pattern: str) -> Path | None:
    cands = []
    if CAMADAS_DIR.exists():
        cands += list(CAMADAS_DIR.glob(pattern))
    cands += list(BASE_DIR.glob(pattern))
    cands = sorted(cands)
    return cands[-1] if cands else None

def caminho_camadas_previsao(var_key: str, data_iso: str | None) -> tuple[Path | None, str]:
    if var_key == "prec_acum":
        p = _latest_file_multi_dirs("prec_acum_*.geojson")
        if not p:
            return None, "Previsão: arquivo não encontrado (prec_acum_*.geojson)"
        return p, f"Previsão: {p.name} (mais recente)"

    if not data_iso:
        return None, "Previsão: sem data"

    if CAMADAS_DIR.exists():
        p1 = CAMADAS_DIR / f"{var_key}_{data_iso}.geojson"
        if p1.exists():
            return p1, f"Previsão: {p1.name} (camadas_geojson)"

    p2 = BASE_DIR / f"{var_key}_{data_iso}.geojson"
    if p2.exists():
        return p2, f"Previsão: {p2.name} (raiz)"

    return None, f"Previsão: arquivo não encontrado ({var_key}_{data_iso}.geojson)"

def carregar_geojson_poligonos_por_classe(path_geojson: Path):
    if not path_geojson or not path_geojson.exists():
        return []

    with open(path_geojson, "r", encoding="utf-8") as f:
        gj = json.load(f)

    feats = gj.get("features", []) or []

    def _ord(ft):
        try:
            return int((ft.get("properties") or {}).get("ordem", 0))
        except Exception:
            return 0

    feats = sorted(feats, key=_ord)
    return feats

def construir_mapa_sobreposicao(var_key: str, data_iso: str | None, camada_unidade: str,
                               mostrar_previsao: bool, mostrar_unidades: bool) -> tuple[go.Figure, str, str]:
    fig = go.Figure()

    lon_min, lon_max, lat_min, lat_max = EXTENT

    # Dois pontos invisíveis pra “forçar” o recorte no Mapbox (sem usar bounds)
    fig.add_trace(
        go.Scattermapbox(
            lat=[lat_min, lat_max],
            lon=[lon_min, lon_max],
            mode="markers",
            marker=dict(size=1, opacity=0),
            hoverinfo="skip",
            showlegend=False,
            name="__fit__",
        )
    )

    status_prev = "Previsão: desligada"
    status_uni = "Unidades: desligadas"

    # --- PREVISÃO (POLÍGONOS) ---
    if mostrar_previsao:
        p, status_prev = caminho_camadas_previsao(var_key, data_iso)
        feats = carregar_geojson_poligonos_por_classe(p) if p else []

        if not feats:
            status_prev = "Previsão: sem features (GeoJSON vazio ou inválido)"

        for i, ft in enumerate(feats):
            props = ft.get("properties", {}) or {}
            label = props.get("label", f"classe {i}")
            hex_color = props.get("hex", "#999999")

            # garante ordem/feature id
            ordem = props.get("ordem", i)
            try:
                ordem = int(ordem)
            except Exception:
                ordem = i

            # garante que properties.ordem exista na feature
            ft.setdefault("properties", {})
            ft["properties"]["ordem"] = ordem

            gj_one = {"type": "FeatureCollection", "features": [ft]}

            # ✅ CHAVE CRÍTICA: featureidkey + locations batendo com properties.ordem
            fig.add_trace(
                go.Choroplethmapbox(
                    geojson=gj_one,
                    featureidkey="properties.ordem",
                    locations=[ordem],
                    z=[1],
                    colorscale=[[0, hex_color], [1, hex_color]],
                    showscale=False,
                    marker_opacity=0.60,
                    marker_line_width=0,                 # sem linha de grade
                    marker_line_color="rgba(0,0,0,0)",   # sem borda
                    name=label,
                    showlegend=True,
                    hovertemplate=f"<b>{label}</b><extra></extra>",
                )
            )

    # --- UNIDADES (PONTOS) ---
    if mostrar_unidades:
        camada_unidade = camada_unidade or "upa"
        arquivo = GEOJSON_FILES.get(camada_unidade)

        lats, lons, custom, status_uni = carregar_geojson_points(arquivo, camada_unidade)

        if lats and lons:
            fig.add_trace(
                go.Scattermapbox(
                    lat=lats,
                    lon=lons,
                    mode="markers",
                    marker=dict(size=7, opacity=0.9, color="black"),  # PRETO (pedido)
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
                    showlegend=True,
                )
            )

    # título
    if var_key == "prec_acum":
        titulo_prev = "Precipitação acumulada no período (mm)"
    else:
        titulo_prev = VAR_OPCOES[var_key]["label"]
        if data_iso:
            titulo_prev += f" – {formatar_label_br(data_iso)}"

    fig.update_layout(
        title=dict(text=f"Sobreposição – {titulo_prev}", x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=45, b=0),
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=(lat_min + lat_max) / 2, lon=(lon_min + lon_max) / 2),
            zoom=3.1,
            fitbounds="locations",  # ✅ recorte fixo (sem “mundo”)
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="left", x=0.0),
    )

    return fig, status_prev, status_uni

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
            "Visualização diária de precipitação e temperatura (ECMWF) + sobreposição com unidades (UPA/UBS/UBSI).",
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
                            "A camada de previsão usa GeoJSON em /camadas_geojson OU na raiz.",
                            className="text-muted",
                        ),
                    ],
                    md=3, lg=3, xl=3,
                ),

                # ✅ só a figura em cima (sem mapa de unidades ao lado)
                dbc.Col(
                    [
                        dcc.Graph(
                            id="graph-mapa",
                            style={"height": "75vh"},
                            config={"scrollZoom": True, "displayModeBar": False},
                        ),
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
                        html.H5("Status de carregamento (debug)", className="mt-2"),
                        html.Ul(id="debug-status", style={"fontSize": "0.95rem"}),
                    ]
                )
            ],
            className="mb-2",
        ),

        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(
                            id="graph-overlay",
                            style={"height": "70vh"},
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
        titulo = info["label"]
        return construir_figura_estatica(src, titulo)

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
    Output("debug-status", "children"),
    Input("dropdown-data", "value"),
    Input("radio-var", "value"),
    Input("dropdown-unidades", "value"),
    Input("check-overlay", "value"),
)
def atualizar_overlay(data_iso, var_key, camada_unidade, check_values):
    check_values = check_values or []
    mostrar_previsao = "prev" in check_values
    mostrar_unidades = "uni" in check_values

    fig, status_prev, status_uni = construir_mapa_sobreposicao(
        var_key=var_key,
        data_iso=data_iso,
        camada_unidade=camada_unidade or "upa",
        mostrar_previsao=mostrar_previsao,
        mostrar_unidades=mostrar_unidades,
    )

    itens = []
    if mostrar_previsao:
        ok = "✅" if ("não encontrado" not in status_prev.lower() and "sem features" not in status_prev.lower()) else "❌"
        itens.append(html.Li([ok + " ", status_prev]))
    else:
        itens.append(html.Li(["ℹ️ Previsão: desligada"]))

    if mostrar_unidades:
        ok = "✅" if ("não encontrado" not in status_uni.lower()) else "❌"
        itens.append(html.Li([ok + " ", f"Unidades ({(camada_unidade or 'upa')}): {status_uni}"]))
    else:
        itens.append(html.Li(["ℹ️ Unidades: desligadas"]))

    return fig, itens

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)



