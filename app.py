# -*- coding: utf-8 -*-
"""
Painel Dash para visualizar as figuras geradas pelo ECMWF (PNGs)
+ Camada interativa com pontos de Unidades de Saúde (UPA/UBS/UBSI) com hover.

Requisitos:
- Subir o arquivo: upa_ubs_ubsi.xlsx (na mesma pasta do app.py no GitHub/Render)
- As abas do Excel:
    UPA  : nm_fantasia, cd_cnes, lon, lat
    UBS  : cd_unidade, cd_cnes, nm_fantasia, cd_mun, lon, lat
    UBSI : cd_dsei, dsei, polo_base, cod_polo, nome_da_es, cd_mun, lon, lat
"""

from pathlib import Path
import base64
from datetime import datetime

import pandas as pd
from dash import Dash, html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

# ----------------- CONFIGURAÇÕES ----------------- #

IMG_DIR = Path(__file__).parent  # pasta onde estão app.py e os PNGs
UNITS_XLSX = IMG_DIR / "upa_ubs_ubsi.xlsx"

# IMPORTANTE: este EXTENT precisa ser o mesmo usado na geração dos PNGs
# (no teu figuras_ecmwf.py aparece: ax.set_extent([-90, -30, -60, 15], crs=ccrs.PlateCarree()))
LON_MIN, LON_MAX = -90.0, -30.0
LAT_MIN, LAT_MAX = -60.0,  15.0

# ----------------- VARIÁVEIS DISPONÍVEIS ----------------- #

VAR_OPCOES = {
    "prec": {
        "label": "Precipitação diária (mm)",
        "prefix": "ecmwf_prec_",
        "usa_data": True,
    },
    "tmin": {
        "label": "Temperatura mínima diária (°C)",
        "prefix": "ecmwf_tmin_",
        "usa_data": True,
    },
    "tmax": {
        "label": "Temperatura máxima diária (°C)",
        "prefix": "ecmwf_tmax_",
        "usa_data": True,
    },
    "tmed": {
        "label": "Temperatura média diária (°C)",
        "prefix": "ecmwf_tmed_",
        "usa_data": True,
    },
    "prec_acum": {
        "label": "Precipitação acumulada no período (mm)",
        "prefix": "ecmwf_prec_acumulada_",
        "usa_data": False,
    },
}

# ----------------- FUNÇÕES AUXILIARES (DATAS/IMAGENS) ----------------- #

def listar_datas_disponiveis():
    """
    Varre a pasta e procura arquivos:
        ecmwf_prec_YYYY-MM-DD.png
    """
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
    """
    Lê o PNG e embute em base64.
    Para 'prec_acum', pega o arquivo acumulado mais recente.
    """
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
        print(f"⚠️ Arquivo não encontrado: {img_path}")
        return ""

    with open(img_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    return f"data:image/png;base64,{encoded}"

# ----------------- FUNÇÕES AUXILIARES (UNIDADES) ----------------- #

def _to_num(series):
    return pd.to_numeric(series, errors="coerce")

def load_unidades_excel(path_xlsx: Path) -> pd.DataFrame:
    """
    Lê UPA/UBS/UBSI do Excel e padroniza colunas para o Dash:
      tipo, nome, cnes, cd_mun, lon, lat, dsei, polo_base, cod_polo
    + calcula x,y normalizados (0..1) para sobrepor no PNG.
    """
    if not path_xlsx.exists():
        print(f"⚠️ Arquivo de unidades não encontrado: {path_xlsx} (seguindo sem pontos)")
        return pd.DataFrame()

    xls = pd.ExcelFile(path_xlsx)

    # --- UPA ---
    upa = pd.read_excel(xls, "UPA")
    upa = upa.rename(columns={"nm_fantasia": "nome", "cd_cnes": "cnes"})
    upa["tipo"] = "UPA"
    if "cd_mun" not in upa.columns:
        upa["cd_mun"] = pd.NA
    upa["dsei"] = pd.NA
    upa["polo_base"] = pd.NA
    upa["cod_polo"] = pd.NA
    upa = upa[["tipo", "nome", "cnes", "cd_mun", "lon", "lat", "dsei", "polo_base", "cod_polo"]]

    # --- UBS ---
    ubs = pd.read_excel(xls, "UBS")
    ubs = ubs.rename(columns={"nm_fantasia": "nome", "cd_cnes": "cnes"})
    ubs["tipo"] = "UBS"
    if "cd_mun" not in ubs.columns:
        ubs["cd_mun"] = pd.NA
    ubs["dsei"] = pd.NA
    ubs["polo_base"] = pd.NA
    ubs["cod_polo"] = pd.NA
    ubs = ubs[["tipo", "nome", "cnes", "cd_mun", "lon", "lat", "dsei", "polo_base", "cod_polo"]]

    # --- UBSI ---
    ubsi = pd.read_excel(xls, "UBSI")
    ubsi = ubsi.rename(columns={"nome_da_es": "nome"})
    ubsi["tipo"] = "UBSI"
    if "cnes" not in ubsi.columns:
        ubsi["cnes"] = pd.NA
    if "cd_mun" not in ubsi.columns:
        ubsi["cd_mun"] = pd.NA
    if "dsei" not in ubsi.columns:
        ubsi["dsei"] = pd.NA
    if "polo_base" not in ubsi.columns:
        ubsi["polo_base"] = pd.NA
    if "cod_polo" not in ubsi.columns:
        ubsi["cod_polo"] = pd.NA
    ubsi = ubsi[["tipo", "nome", "cnes", "cd_mun", "lon", "lat", "dsei", "polo_base", "cod_polo"]]

    df = pd.concat([upa, ubs, ubsi], ignore_index=True)

    # lon/lat numéricos
    df["lon"] = _to_num(df["lon"])
    df["lat"] = _to_num(df["lat"])
    df = df.dropna(subset=["lon", "lat"]).copy()

    # x,y normalizados (0..1)
    df["x"] = (df["lon"] - LON_MIN) / (LON_MAX - LON_MIN)
    df["y"] = (df["lat"] - LAT_MIN) / (LAT_MAX - LAT_MIN)

    # mantém apenas dentro do quadro do PNG
    df = df[df["x"].between(0, 1) & df["y"].between(0, 1)].copy()

    # strings p/ hover
    for col in ["nome", "tipo", "cnes", "cd_mun", "dsei", "polo_base", "cod_polo"]:
        if col in df.columns:
            df[col] = df[col].astype("string").fillna("")

    return df

def add_unidades_layer(fig: go.Figure, df_units: pd.DataFrame) -> go.Figure:
    """
    Sobrepõe pontos (x,y) sobre a imagem (0..1) com hover.
    """
    if df_units is None or df_units.empty:
        return fig

    # cores por tipo (simples e legível)
    color_map = {"UPA": "red", "UBS": "blue", "UBSI": "green"}
    colors = df_units["tipo"].map(color_map).fillna("black")

    custom = df_units[["nome", "tipo", "cnes", "cd_mun", "dsei", "polo_base", "cod_polo", "lat", "lon"]].values

    fig.add_trace(
        go.Scatter(
            x=df_units["x"],
            y=df_units["y"],
            mode="markers",
            name="Unidades de Saúde",
            marker=dict(size=6, opacity=0.85, color=colors),
            customdata=custom,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Tipo: %{customdata[1]}<br>"
                "CNES: %{customdata[2]}<br>"
                "CD_MUN: %{customdata[3]}<br>"
                "DSEI: %{customdata[4]}<br>"
                "Polo: %{customdata[5]} (%{customdata[6]})<br>"
                "Lat/Lon: %{customdata[7]:.3f}, %{customdata[8]:.3f}"
                "<extra></extra>"
            ),
        )
    )
    return fig

# ----------------- FIGURAS (ESTÁTICA/ANIMAÇÃO) ----------------- #

def construir_figura_estatica(src: str, titulo: str, df_units: pd.DataFrame, mostrar_unidades: bool) -> go.Figure:
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
        margin=dict(l=0, r=0, t=50, b=0),
        dragmode="pan",
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    if mostrar_unidades and src:
        fig = add_unidades_layer(fig, df_units)

    return fig


def construir_animacao(var_key: str, datas_iso: list[str], titulo: str, df_units: pd.DataFrame, mostrar_unidades: bool) -> go.Figure:
    if len(datas_iso) == 0:
        return construir_figura_estatica("", "Sem dados para animar", df_units, False)

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

    # pontos fixos (não mudam por frame) — adiciona uma vez
    if mostrar_unidades and (df_units is not None) and (not df_units.empty):
        fig = add_unidades_layer(fig, df_units)

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
            args=[[f.name], {
                "mode": "immediate",
                "frame": {"duration": 500, "redraw": True},
                "transition": {"duration": 0},
            }],
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
                    args=[
                        None,
                        {
                            "frame": {"duration": 500, "redraw": True},
                            "fromcurrent": True,
                            "transition": {"duration": 0},
                        },
                    ],
                )
            ],
        )
    ]

    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=50, b=40),
        dragmode="pan",
        sliders=sliders,
        updatemenus=updatemenus,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig

# ----------------- PREPARA LISTAS E DADOS ----------------- #

DATAS = listar_datas_disponiveis()
if not DATAS:
    raise RuntimeError(
        f"Nenhuma data diária encontrada em {IMG_DIR}. "
        f"Certifique-se de que existam arquivos ecmwf_prec_YYYY-MM-DD.png."
    )
DATA_DEFAULT = DATAS[-1]

# carrega unidades uma vez (em memória)
DF_UNITS = load_unidades_excel(UNITS_XLSX)

# ----------------- APP DASH ----------------- #

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # pro Render/gunicorn
app.title = "Previsão ECMWF - Painel de Mapas"

app.layout = dbc.Container(
    [
        html.H2(
            "Painel de Monitoramento Meteorológico - CGCLIMA/SSCLIMA",
            className="mt-3 mb-2",
            style={"textAlign": "center"},
        ),

        html.Div(
            "Visualização diária de precipitação e temperatura a partir da previsão ECMWF.",
            className="mb-3",
            style={"textAlign": "center"},
        ),

        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H5("Campos de seleção", className="mb-3"),

                        html.Label("Variável:", className="fw-bold"),
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

                        html.Label("Modo de visualização:", className="fw-bold"),
                        dcc.RadioItems(
                            id="radio-modo",
                            options=[
                                {"label": "Mapa diário", "value": "dia"},
                                {"label": "Animação (todos os dias)", "value": "anim"},
                            ],
                            value="dia",
                            labelStyle={"display": "block"},
                        ),
                        html.Small(
                            "Obs: Animação não se aplica à precipitação acumulada; nesse caso, o mapa é estático.",
                            className="text-muted",
                        ),

                        html.Hr(),

                        dbc.Checklist(
                            id="check-unidades",
                            options=[{"label": "Mostrar Unidades de Saúde (UPA/UBS/UBSI)", "value": "on"}],
                            value=["on"],
                            switch=True,
                            className="mt-2",
                        ),
                        html.Small(
                            f"Unidades carregadas: {len(DF_UNITS) if DF_UNITS is not None else 0}",
                            className="text-muted",
                        ),
                    ],
                    md=3, lg=3, xl=3,
                ),

                dbc.Col(
                    [
                        dcc.Graph(
                            id="graph-mapa",
                            style={"height": "85vh"},
                            config={
                                "scrollZoom": True,
                                "displayModeBar": False,
                            },
                        ),
                    ],
                    md=9, lg=9, xl=9,
                ),
            ],
            className="mb-3",
        ),

        html.Hr(),
        html.Footer(
            "Fonte: ECMWF Open Data – Processamento local (Pedro / Dash)",
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
    Input("check-unidades", "value"),
)
def atualizar_mapa(data_iso, var_key, modo, unidades_on):
    mostrar_unidades = isinstance(unidades_on, list) and ("on" in unidades_on)

    if var_key is None:
        return go.Figure()

    info = VAR_OPCOES[var_key]

    # precipitação acumulada: pega png mais recente
    if var_key == "prec_acum":
        src = carregar_imagem_base64("prec_acum", None)
        titulo = info["label"]
        return construir_figura_estatica(src, titulo, DF_UNITS, mostrar_unidades)

    # diário
    if modo == "dia":
        if data_iso is None:
            return go.Figure()
        titulo = f"{info['label']} – {formatar_label_br(data_iso)}"
        src = carregar_imagem_base64(var_key, data_iso)
        return construir_figura_estatica(src, titulo, DF_UNITS, mostrar_unidades)

    # animação
    titulo = f"{info['label']} – (animação)"
    return construir_animacao(var_key, DATAS, titulo, DF_UNITS, mostrar_unidades)

# ----------------- MAIN (LOCAL) ----------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)

    app.run(host="0.0.0.0", port=8050, debug=True)

