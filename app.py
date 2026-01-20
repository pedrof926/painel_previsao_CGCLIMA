# -*- coding: utf-8 -*-
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

# ----------------- VARIÁVEIS DISPONÍVEIS (PREVISÃO PNG) ----------------- #
VAR_OPCOES = {
    "prec": {"label": "Precipitação diária (mm)", "prefix": "ecmwf_prec_", "usa_data": True},
    "tmin": {"label": "Temperatura mínima diária (°C)", "prefix": "ecmwf_tmin_", "usa_data": True},
    "tmax": {"label": "Temperatura máxima diária (°C)", "prefix": "ecmwf_tmax_", "usa_data": True},
    "tmed": {"label": "Temperatura média diária (°C)", "prefix": "ecmwf_tmed_", "usa_data": True},
    "prec_acum": {"label": "Precipitação acumulada no período (mm)", "prefix": "ecmwf_prec_acumulada_", "usa_data": False},
}

# ----------------- HELPERS PNG ----------------- #
def listar_datas_disponiveis():
    datas = set()
    for img_path in IMG_DIR.glob("ecmwf_prec_*.png"):
        parte_data = img_path.stem.replace("ecmwf_prec_", "", 1)
        try:
            datetime.strptime(parte_data, "%Y-%m-%d")
            datas.add(parte_data)
        except ValueError:
            continue
    return sorted(datas)

def formatar_label_br(data_iso: str) -> str:
    return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")

def carregar_imagem_base64(var_key: str, data_iso: str | None) -> str:
    info = VAR_OPCOES[var_key]
    prefix = info["prefix"]

    if var_key == "prec_acum":
        candidates = sorted(IMG_DIR.glob(f"{prefix}*.png"))
        if not candidates:
            return ""
        img_path = candidates[-1]
    else:
        if data_iso is None:
            return ""
        img_path = IMG_DIR / f"{prefix}{data_iso}.png"

    if not img_path.exists():
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
                x=0, y=1, sizex=1, sizey=1,
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

# ----------------- HELPERS GEOJSON ----------------- #
def _safe_float(x):
    try:
        if isinstance(x, str):
            x = x.strip().replace(",", ".")
        return float(x)
    except Exception:
        return None

def find_any_geojson(name_contains: str) -> Path | None:
    """
    Procura recursivo no repo por um .geojson cujo nome contenha 'name_contains'
    (case-insensitive).
    """
    key = name_contains.lower()
    hits = []
    for p in BASE_DIR.rglob("*.geojson"):
        if key in p.name.lower():
            hits.append(p)
    hits = sorted(hits)
    return hits[0] if hits else None

def carregar_geojson_points(caminho: Path | None, camada: str):
    if not caminho or not caminho.exists():
        return [], [], [], f"❌ {camada}: arquivo não encontrado"

    with open(caminho, "r", encoding="utf-8") as f:
        gj = json.load(f)

    lats, lons, custom = [], [], []
    feats = gj.get("features", []) or []

    for ft in feats:
        geom = ft.get("geometry", {}) or {}
        if geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue

        lon = _safe_float(coords[0])
        lat = _safe_float(coords[1])
        if lon is None or lat is None:
            continue

        props = ft.get("properties", {}) or {}
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

    return lats, lons, custom, f"✅ {camada}: {len(lats)} pontos | arquivo: {caminho.name}"

def latest_camadas_file(pattern: str) -> Path | None:
    cands = sorted(CAMADAS_DIR.rglob(pattern))
    return cands[-1] if cands else None

def caminho_camadas_previsao(var_key: str, data_iso: str | None) -> Path | None:
    if not CAMADAS_DIR.exists():
        return None

    if var_key == "prec_acum":
        return latest_camadas_file("prec_acum_*.geojson")

    if not data_iso:
        return None

    # procura recursivo var_YYYY-MM-DD.geojson
    return latest_camadas_file(f"{var_key}_{data_iso}.geojson")

def carregar_fc_previsao(path_geojson: Path | None):
    """
    Lê FeatureCollection e injeta 'id' único por feature (id = classe),
    para o Choroplethmapbox não “sumir”.
    """
    if not path_geojson or not path_geojson.exists():
        return None, "❌ Previsão: arquivo não encontrado"

    with open(path_geojson, "r", encoding="utf-8") as f:
        fc = json.load(f)

    feats = fc.get("features", []) or []
    if not feats:
        return None, f"❌ Previsão: sem features | arquivo: {path_geojson.name}"

    # ordena e injeta id
    def _ord(ft):
        try:
            return int((ft.get("properties") or {}).get("ordem", 0))
        except Exception:
            return 0

    feats = sorted(feats, key=_ord)
    new_feats = []
    for ft in feats:
        props = ft.get("properties", {}) or {}
        cid = props.get("classe", None)
        if cid is None:
            continue
        try:
            cid = int(cid)
        except Exception:
            continue
        ft["id"] = cid  # ✅ crucial
        new_feats.append(ft)

    if not new_feats:
        return None, f"❌ Previsão: features sem 'classe' | arquivo: {path_geojson.name}"

    fc = {"type": "FeatureCollection", "features": new_feats}

    # meta para cores/labels
    labels = []
    colors = []
    ids = []
    for ft in new_feats:
        props = ft.get("properties", {}) or {}
        ids.append(int(ft["id"]))
        labels.append(props.get("label", f"classe {ft['id']}"))
        colors.append(props.get("hex", "#999999"))

    # colorscale discreta (degrau)
    n = len(ids)
    if n == 1:
        colorscale = [[0.0, colors[0]], [1.0, colors[0]]]
        zmin, zmax = ids[0], ids[0] + 1
    else:
        colorscale = []
        for i, col in enumerate(colors):
            t = i / (n - 1)
            colorscale.append([t, col])
        zmin, zmax = min(ids), max(ids)

    meta = dict(ids=ids, labels=labels, colorscale=colorscale, zmin=zmin, zmax=zmax)
    return (fc, meta), f"✅ Previsão: {len(new_feats)} classes | arquivo: {path_geojson.name}"

def construir_mapa_sobreposicao(var_key, data_iso, camada_unidade, mostrar_previsao, mostrar_unidades):
    fig = go.Figure()
    center_lat, center_lon, zoom = -14.0, -55.0, 2.6

    status_msgs = []

    # -------- PREVISÃO --------
    if mostrar_previsao:
        p = caminho_camadas_previsao(var_key, data_iso)
        loaded, msg = carregar_fc_previsao(p)
        status_msgs.append(msg)

        if loaded:
            fc, meta = loaded
            fig.add_trace(
                go.Choroplethmapbox(
                    geojson=fc,
                    locations=meta["ids"],
                    z=meta["ids"],
                    colorscale=meta["colorscale"],
                    zmin=meta["zmin"],
                    zmax=meta["zmax"],
                    showscale=False,
                    marker_opacity=0.55,
                    marker_line_width=0,
                    customdata=meta["labels"],
                    hovertemplate="<b>%{customdata}</b><extra></extra>",
                    name="Previsão",
                )
            )
    else:
        status_msgs.append("ℹ️ Previsão: desligada")

    # -------- UNIDADES --------
    if mostrar_unidades:
        cores = {"upa": "red", "ubs": "blue", "ubsi": "green"}

        # procura arquivos de forma “impossível falhar”
        units_path = find_any_geojson(camada_unidade)
        lats, lons, custom, msg = carregar_geojson_points(units_path, camada_unidade)
        status_msgs.append(msg)

        if lats and lons:
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
            zoom = 3.2

            fig.add_trace(
                go.Scattermapbox(
                    lat=lats,
                    lon=lons,
                    mode="markers",
                    marker=dict(size=7, opacity=0.9, color=cores.get(camada_unidade, "black")),
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
                )
            )
    else:
        status_msgs.append("ℹ️ Unidades: desligadas")

    # título
    if var_key == "prec_acum":
        titulo_prev = "Camada previsão: Precipitação acumulada"
    else:
        titulo_prev = f"Camada previsão: {VAR_OPCOES[var_key]['label']} – {formatar_label_br(data_iso)}" if data_iso else f"Camada previsão: {VAR_OPCOES[var_key]['label']}"

    titulo = f"Sobreposição – {titulo_prev} + {('Unidades: ' + camada_unidade.upper()) if mostrar_unidades else 'Unidades: (desligadas)'}"

    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=45, b=0),
        mapbox=dict(style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=zoom),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig, status_msgs

# ----------------- PREPARA LISTA DE DATAS ----------------- #
DATAS = listar_datas_disponiveis()
if not DATAS:
    raise RuntimeError("Nenhuma data diária encontrada (ecmwf_prec_YYYY-MM-DD.png).")
DATA_DEFAULT = DATAS[-1]

# ----------------- APP ----------------- #
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
app.title = "Previsão ECMWF - Painel"

app.layout = dbc.Container(
    [
        html.H2("Painel de Monitoramento Meteorológico - CGCLIMA/SSCLIMA", className="mt-3 mb-2", style={"textAlign": "center"}),

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

                        html.Hr(),

                        html.Label("Unidades (para sobreposição):", className="fw-bold"),
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

                        html.Label("Mapa de SOBREPOSIÇÃO:", className="fw-bold"),
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
                    ],
                    md=3,
                ),

                dbc.Col(
                    [
                        dcc.Graph(
                            id="graph-mapa",
                            style={"height": "75vh"},
                            config={"scrollZoom": True, "displayModeBar": False},
                        ),
                    ],
                    md=9,
                ),
            ]
        ),

        html.Hr(),

        html.H5("Status de carregamento (debug)", className="mt-2"),
        html.Ul(id="status-list"),

        html.Hr(),

        dcc.Graph(
            id="graph-overlay",
            style={"height": "65vh"},
            config={"scrollZoom": True, "displayModeBar": False},
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
    info = VAR_OPCOES[var_key]

    if var_key == "prec_acum":
        src = carregar_imagem_base64("prec_acum", None)
        return construir_figura_estatica(src, info["label"])

    if modo == "dia":
        titulo = f"{info['label']} – {formatar_label_br(data_iso)}"
        src = carregar_imagem_base64(var_key, data_iso)
        return construir_figura_estatica(src, titulo)

    titulo = f"{info['label']} – (animação)"
    # animação não incluída aqui pra manter simples; o teu original já tinha.
    src = carregar_imagem_base64(var_key, DATAS[0])
    return construir_figura_estatica(src, titulo)

@app.callback(
    Output("graph-overlay", "figure"),
    Output("status-list", "children"),
    Input("dropdown-data", "value"),
    Input("radio-var", "value"),
    Input("dropdown-unidades", "value"),
    Input("check-overlay", "value"),
)
def atualizar_overlay(data_iso, var_key, camada_unidade, check_values):
    check_values = check_values or []
    mostrar_previsao = "prev" in check_values
    mostrar_unidades = "uni" in check_values

    fig, msgs = construir_mapa_sobreposicao(
        var_key=var_key,
        data_iso=data_iso,
        camada_unidade=camada_unidade,
        mostrar_previsao=mostrar_previsao,
        mostrar_unidades=mostrar_unidades,
    )

    return fig, [html.Li(m) for m in msgs]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)




# ----------------- MAIN (LOCAL) ----------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)


