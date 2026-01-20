# -*- coding: utf-8 -*-
"""
Painel Dash para visualizar as figuras geradas pelo ECMWF + mapa de SOBREPOSIÇÃO
(camada previsão GeoJSON + pontos de unidades UPA/UBS/UBSI).

Arquivos esperados no repo (Render):
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
    Preferencialmente em: camadas_geojson/
      prec_YYYY-MM-DD.geojson
      tmin_YYYY-MM-DD.geojson
      tmax_YYYY-MM-DD.geojson
      tmed_YYYY-MM-DD.geojson
      prec_acum_YYYY-MM-DD_a_YYYY-MM-DD.geojson
    MAS o app também procura na RAIZ do repo (fallback).
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

# Procura camadas aqui:
CAMADAS_DIR = BASE_DIR / "camadas_geojson"
# ...e também aqui (caso você tenha upado tudo na raiz sem querer):
CAMADAS_FALLBACK_DIRS = [CAMADAS_DIR, BASE_DIR]

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
        return [], [], [], f"⚠️ {camada}: arquivo não encontrado ({caminho.name})"

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            gj = json.load(f)
    except Exception as e:
        return [], [], [], f"⚠️ {camada}: erro lendo GeoJSON ({caminho.name}) -> {e}"

    lats, lons, custom = [], [], []
    feats = gj.get("features", []) or []

    for ft in feats:
        geom = ft.get("geometry", {}) or {}
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

    return lats, lons, custom, f"✅ {camada}: {len(lats)} pontos | arquivo: {caminho.name}"

# ----------------- HELPERS (CAMADAS PREVISÃO GEOJSON) ----------------- #
def _parse_date_from_name(name: str) -> str | None:
    # espera ..._YYYY-MM-DD.geojson
    try:
        base = Path(name).stem
        parts = base.split("_")
        cand = parts[-1]
        datetime.strptime(cand, "%Y-%m-%d")
        return cand
    except Exception:
        return None

def _latest_file_in_dirs(pattern: str) -> Path | None:
    candidates = []
    for d in CAMADAS_FALLBACK_DIRS:
        if d.exists():
            candidates += list(d.glob(pattern))
    candidates = sorted({c.resolve() for c in candidates})  # uniq
    return candidates[-1] if candidates else None

def _best_match_date_file(var_key: str, data_iso: str) -> tuple[Path | None, str]:
    """
    Tenta:
    1) arquivo exato var_YYYY-MM-DD.geojson
    2) se não existir, usa o mais recente <= data_iso
    3) se ainda não, usa o mais recente disponível
    Retorna (path, msg_debug)
    """
    # 1) exato
    for d in CAMADAS_FALLBACK_DIRS:
        p = d / f"{var_key}_{data_iso}.geojson"
        if p.exists():
            return p, f"✅ Previsão: {p.name} (data exata)"

    # 2) melhor <= data_iso
    target = datetime.strptime(data_iso, "%Y-%m-%d")
    all_files = []
    for d in CAMADAS_FALLBACK_DIRS:
        if d.exists():
            all_files += list(d.glob(f"{var_key}_*.geojson"))

    dated = []
    for p in all_files:
        di = _parse_date_from_name(p.name)
        if di:
            dated.append((datetime.strptime(di, "%Y-%m-%d"), p))

    if dated:
        dated.sort(key=lambda x: x[0])
        leq = [x for x in dated if x[0] <= target]
        if leq:
            chosen = leq[-1][1]
            return chosen, f"⚠️ Previsão: {chosen.name} (fallback <= {data_iso})"
        # 3) mais recente
        chosen = dated[-1][1]
        return chosen, f"⚠️ Previsão: {chosen.name} (fallback mais recente)"

    return None, "❌ Previsão: arquivo não encontrado (nenhum GeoJSON disponível)"

def caminho_camadas_previsao(var_key: str, data_iso: str | None) -> tuple[Path | None, str]:
    """
    - prec/tmin/tmax/tmed: var_YYYY-MM-DD.geojson
    - prec_acum: prec_acum_YYYY-MM-DD_a_YYYY-MM-DD.geojson (pega o mais recente)
    """
    if var_key == "prec_acum":
        p = _latest_file_in_dirs("prec_acum_*.geojson")
        if p:
            return p, f"✅ Previsão (acum): {p.name} (mais recente)"
        return None, "❌ Previsão (acum): arquivo não encontrado"

    if not data_iso:
        return None, "❌ Previsão: data não selecionada"

    return _best_match_date_file(var_key, data_iso)

def carregar_geojson_poligonos_por_classe(path_geojson: Path | None):
    if not path_geojson or not path_geojson.exists():
        return []

    try:
        with open(path_geojson, "r", encoding="utf-8") as f:
            gj = json.load(f)
    except Exception:
        return []

    feats = gj.get("features", []) or []

    def _ord(ft):
        try:
            return int((ft.get("properties") or {}).get("ordem", 0))
        except Exception:
            return 0

    return sorted(feats, key=_ord)

def construir_mapa_sobreposicao(var_key: str, data_iso: str | None, camada_unidade: str,
                               mostrar_previsao: bool, mostrar_unidades: bool) -> tuple[go.Figure, list[str]]:
    """
    Retorna (fig, debug_lines)
    """
    fig = go.Figure()
    debug_lines = []

    # centro default (América do Sul)
    center_lat, center_lon, zoom = -14.0, -55.0, 2.6

    # --- PREVISÃO (POLÍGONOS) ---
    titulo_prev = "Camada previsão: (desligada)"
    if mostrar_previsao:
        p, msg_prev = caminho_camadas_previsao(var_key, data_iso)
        debug_lines.append(msg_prev)

        feats = carregar_geojson_poligonos_por_classe(p) if p else []
        if feats:
            for i, ft in enumerate(feats):
                props = ft.get("properties", {}) or {}
                label = props.get("label", f"classe {i}")
                hex_color = props.get("hex", "#999999")

                gj_one = {"type": "FeatureCollection", "features": [ft]}

                fig.add_trace(
                    go.Choroplethmapbox(
                        geojson=gj_one,
                        locations=[0],
                        z=[1],
                        colorscale=[[0, hex_color], [1, hex_color]],
                        showscale=False,
                        marker_opacity=0.55,
                        marker_line_width=0,
                        name=label,
                        hovertemplate=f"<b>{label}</b><extra></extra>",
                    )
                )

            if var_key == "prec_acum":
                titulo_prev = "Camada previsão: Precipitação acumulada"
            else:
                titulo_prev = f"Camada previsão: {VAR_OPCOES[var_key]['label']} – {formatar_label_br(data_iso)}" if data_iso else f"Camada previsão: {VAR_OPCOES[var_key]['label']}"
        else:
            if var_key == "prec_acum":
                titulo_prev = "Camada previsão: Precipitação acumulada (vazia)"
            else:
                titulo_prev = f"Camada previsão: {VAR_OPCOES[var_key]['label']} – {formatar_label_br(data_iso)} (vazia)" if data_iso else f"Camada previsão: {VAR_OPCOES[var_key]['label']} (vazia)"
    else:
        debug_lines.append("ℹ️ Previsão: desligada")

    # --- UNIDADES (PONTOS) ---
    if mostrar_unidades:
        arquivo = GEOJSON_FILES.get(camada_unidade)
        lats, lons, custom, msg_uni = carregar_geojson_points(arquivo, camada_unidade)
        debug_lines.append(msg_uni)

        if lats and lons:
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
            zoom = 3.2

            cores = {"upa": "red", "ubs": "blue", "ubsi": "green"}

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
        debug_lines.append("ℹ️ Unidades: desligadas")

    titulo = f"Sobreposição – {titulo_prev} + {('Unidades: ' + camada_unidade.upper()) if mostrar_unidades else 'Unidades: (desligadas)'}"

    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=45, b=0),
        mapbox=dict(style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=zoom),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.08, xanchor="left", x=0.0),
    )
    return fig, debug_lines

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
                            "Camadas de previsão: procura em /camadas_geojson e também na raiz do repo (fallback).",
                            className="text-muted",
                        ),
                    ],
                    md=3, lg=3, xl=3,
                ),

                # Direita: SOMENTE A FIGURA (PNG)
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

        # Debug + overlay
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H5("Mapa de SOBREPOSIÇÃO", className="mt-2"),
                        dcc.Markdown(id="debug-overlay", className="mb-2"),
                        dcc.Graph(
                            id="graph-overlay",
                            style={"height": "65vh"},
                            config={"scrollZoom": True, "displayModeBar": False},
                        ),
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
    Output("debug-overlay", "children"),
    Input("dropdown-data", "value"),
    Input("radio-var", "value"),
    Input("dropdown-unidades", "value"),
    Input("check-overlay", "value"),
)
def atualizar_overlay(data_iso, var_key, camada_unidade, check_values):
    check_values = check_values or []
    mostrar_previsao = "prev" in check_values
    mostrar_unidades = "uni" in check_values

    fig, debug_lines = construir_mapa_sobreposicao(
        var_key=var_key,
        data_iso=data_iso,
        camada_unidade=camada_unidade or "upa",
        mostrar_previsao=mostrar_previsao,
        mostrar_unidades=mostrar_unidades,
    )

    md = "### Status de carregamento (debug)\n"
    for line in debug_lines:
        if line.startswith("✅"):
            md += f"- ✅ {line[1:].strip()}\n"
        elif line.startswith("⚠️"):
            md += f"- ⚠️ {line[1:].strip()}\n"
        elif line.startswith("❌"):
            md += f"- ❌ {line[1:].strip()}\n"
        else:
            md += f"- {line}\n"

    return fig, md

# ----------------- MAIN (LOCAL) ----------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)





# ----------------- MAIN (LOCAL) ----------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)


