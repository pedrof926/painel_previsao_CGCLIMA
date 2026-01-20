# -*- coding: utf-8 -*-
"""
Painel Dash para visualizar as figuras geradas pelo ECMWF + mapa de SOBREPOSIÇÃO
(camada previsão GeoJSON + pontos de unidades UPA/UBS/UBSI).

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

- Camadas previsão (GeoJSON MultiPolygon por classe) em:
    camadas_geojson/
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

# arquivos “preferidos”
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
    dt = datetime.strptime(data_iso, "%Y-%m-%d")
    return dt.strftime("%d/%m/%Y")

def carregar_imagem_base64(var_key: str, data_iso: str | None) -> str:
    info = VAR_OPCOES[var_key]
    prefix = info["prefix"]

    if var_key == "prec_acum":
        candidates = sorted(IMG_DIR.glob(f"{prefix}*.png"))
        if not candidates:
            print(f"⚠️ Nenhuma imagem acumulada encontrada: {prefix}*.png")
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
                source=src0, xref="x", yref="y",
                x=0, y=1, sizex=1, sizey=1,
                sizing="stretch", layer="below",
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
            x=0.0, y=1.05, xanchor="left", yanchor="top",
            buttons=[dict(
                label="▶ Play", method="animate",
                args=[None, {"frame": {"duration": 500, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0}}],
            )],
        )],
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig

# ----------------- HELPERS (UNIDADES) ----------------- #
def _safe_float(x):
    try:
        if isinstance(x, str):
            x = x.strip().replace(",", ".")
        return float(x)
    except Exception:
        return None

def _find_geojson_units(camada_key: str) -> Path | None:
    """
    Resolve o arquivo da camada:
    - tenta o caminho direto (BASE_DIR/upa.geojson etc)
    - se não achar, procura recursivo no repo (Render às vezes muda cwd/estrutura)
    """
    preferred = GEOJSON_FILES.get(camada_key)
    if preferred and preferred.exists():
        return preferred

    # tenta variações de case
    for name in [f"{camada_key}.geojson", f"{camada_key.upper()}.geojson", f"{camada_key.capitalize()}.geojson"]:
        p = BASE_DIR / name
        if p.exists():
            return p

    # busca recursiva
    hits = sorted(BASE_DIR.rglob(f"{camada_key}.geojson"))
    if hits:
        return hits[0]

    print(f"⚠️ Unidades: não encontrei arquivo para '{camada_key}' no repo.")
    return None

def carregar_geojson_points(caminho: Path | None, camada: str):
    if not caminho or not caminho.exists():
        print(f"⚠️ GeoJSON de unidades não encontrado para {camada}: {caminho}")
        return [], [], []

    with open(caminho, "r", encoding="utf-8") as f:
        gj = json.load(f)

    lats, lons, custom = [], [], []
    feats = gj.get("features", []) or []

    for ft in feats:
        geom = ft.get("geometry", {}) or {}
        props = ft.get("properties", {}) or {}

        if geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue

        lon = _safe_float(coords[0])
        lat = _safe_float(coords[1])
        if lon is None or lat is None:
            continue

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

    return lats, lons, custom

# ----------------- HELPERS (CAMADAS PREVISÃO GEOJSON) ----------------- #
def _latest_file(pattern: str) -> Path | None:
    cands = sorted(CAMADAS_DIR.glob(pattern))
    return cands[-1] if cands else None

def caminho_camadas_previsao(var_key: str, data_iso: str | None) -> Path | None:
    """
    Deixa robusto:
    - tenta camadas_geojson/var_YYYY-MM-DD.geojson
    - tenta camadas_geojson/var/var_YYYY-MM-DD.geojson
    - prec_acum: pega o mais recente prec_acum_*.geojson (em qualquer subpasta também)
    """
    if not CAMADAS_DIR.exists():
        print(f"⚠️ Pasta camadas_geojson não encontrada: {CAMADAS_DIR}")
        return None

    if var_key == "prec_acum":
        p = _latest_file("prec_acum_*.geojson")
        if p:
            return p
        # tenta recursivo
        hits = sorted(CAMADAS_DIR.rglob("prec_acum_*.geojson"))
        return hits[-1] if hits else None

    if not data_iso:
        return None

    # 1) padrão novo
    p1 = CAMADAS_DIR / f"{var_key}_{data_iso}.geojson"
    if p1.exists():
        return p1

    # 2) se tiver em subpasta var/
    p2 = CAMADAS_DIR / var_key / f"{var_key}_{data_iso}.geojson"
    if p2.exists():
        return p2

    # 3) fallback recursivo
    hits = sorted(CAMADAS_DIR.rglob(f"{var_key}_{data_iso}.geojson"))
    if hits:
        return hits[0]

    print(f"⚠️ Camada previsão não encontrada para {var_key} {data_iso}")
    return None

def carregar_fc_previsao(path_geojson: Path | None):
    """
    Lê FeatureCollection e extrai:
    - locations/z = classe (int)
    - cores = hex
    - labels = label
    Também cria colorscale discreta (classe -> cor) pra Choroplethmapbox.
    """
    if not path_geojson or not path_geojson.exists():
        return None, None

    with open(path_geojson, "r", encoding="utf-8") as f:
        fc = json.load(f)

    feats = fc.get("features", []) or []
    if not feats:
        return None, None

    # ordena por ordem
    def _ord(ft):
        try:
            return int((ft.get("properties") or {}).get("ordem", 0))
        except Exception:
            return 0

    feats = sorted(feats, key=_ord)
    fc = {"type": "FeatureCollection", "features": feats}

    classes = []
    labels = []
    colors = []
    for ft in feats:
        props = ft.get("properties", {}) or {}
        cid = props.get("classe")
        if cid is None:
            continue
        try:
            cid = int(cid)
        except Exception:
            continue
        classes.append(cid)
        labels.append(props.get("label", f"classe {cid}"))
        colors.append(props.get("hex", "#999999"))

    if not classes:
        return None, None

    # colorscale discreta
    # Normaliza 0..1 usando (n-1). Se só 1 classe, fixa em 0.
    n = len(classes)
    if n == 1:
        colorscale = [[0.0, colors[0]], [1.0, colors[0]]]
    else:
        colorscale = []
        for i, col in enumerate(colors):
            t0 = i / (n - 1)
            # “degrau” (repete o ponto) pra ficar discreto
            colorscale.append([t0, col])

    meta = {
        "classes": classes,
        "labels": labels,
        "colors": colors,
        "colorscale": colorscale,
    }
    return fc, meta

def construir_mapa_sobreposicao(var_key: str, data_iso: str | None, camada_unidade: str,
                               mostrar_previsao: bool, mostrar_unidades: bool) -> go.Figure:
    fig = go.Figure()

    # centro default (América do Sul)
    center_lat, center_lon, zoom = -14.0, -55.0, 2.6

    # --- PREVISÃO (POLÍGONOS) ---
    if mostrar_previsao:
        p = caminho_camadas_previsao(var_key, data_iso)
        fc, meta = carregar_fc_previsao(p)

        if fc and meta:
            # ✅ 1 trace só (bem mais estável no Render)
            fig.add_trace(
                go.Choroplethmapbox(
                    geojson=fc,
                    featureidkey="properties.classe",
                    locations=meta["classes"],
                    z=meta["classes"],  # só pra mapear cor (via colorscale)
                    colorscale=meta["colorscale"],
                    zmin=min(meta["classes"]),
                    zmax=max(meta["classes"]) if len(meta["classes"]) > 1 else min(meta["classes"]) + 1,
                    showscale=False,
                    marker_opacity=0.55,
                    marker_line_width=0,
                    customdata=meta["labels"],
                    hovertemplate="<b>%{customdata}</b><extra></extra>",
                    name="Previsão",
                )
            )
        else:
            print(f"⚠️ Previsão: FC/meta vazios. Arquivo: {p}")

        if var_key == "prec_acum":
            titulo_prev = "Camada previsão: Precipitação acumulada"
        else:
            titulo_prev = (
                f"Camada previsão: {VAR_OPCOES[var_key]['label']} – {formatar_label_br(data_iso)}"
                if data_iso else f"Camada previsão: {VAR_OPCOES[var_key]['label']}"
            )
    else:
        titulo_prev = "Camada previsão: (desligada)"

    # --- UNIDADES (PONTOS) ---
    if mostrar_unidades:
        cores = {"upa": "red", "ubs": "blue", "ubsi": "green"}
        arquivo = _find_geojson_units(camada_unidade)
        lats, lons, custom = carregar_geojson_points(arquivo, camada_unidade)

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

    titulo = f"Sobreposição – {titulo_prev} + {('Unidades: ' + camada_unidade.upper()) if mostrar_unidades else 'Unidades: (desligadas)'}"

    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=45, b=0),
        mapbox=dict(style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=zoom),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
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

                        html.Label("Unidades de Saúde (para o mapa de sobreposição):", className="fw-bold"),
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
                                {"label": "Mostrar camada de previsão (GeoJSON)", "value": "prev"},
                                {"label": "Mostrar unidades (pontos)", "value": "uni"},
                            ],
                            value=["prev", "uni"],
                            labelStyle={"display": "block"},
                            className="mb-2",
                        ),
                        html.Small(
                            "A camada de previsão usa os GeoJSON em /camadas_geojson.",
                            className="text-muted",
                        ),
                    ],
                    md=3, lg=3, xl=3,
                ),

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



# ----------------- MAIN (LOCAL) ----------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)


