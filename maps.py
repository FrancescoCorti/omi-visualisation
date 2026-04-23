"""
Italian Real Estate Dashboard
==============================
Combines choropleth maps (Folium/GeoPandas) with price trend charts (Plotly) in a Dash app.

Requirements:
    pip install dash dash-bootstrap-components geopandas folium plotly pandas

Run:
    python dashboard.py  →  http://127.0.0.1:8050
"""

import pandas as pd
import geopandas as gpd
import folium
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc


# ── 1. Load & pre-process geodata at startup ─────────────────────────────────
#    All simplification happens once here, not on every callback.

gdf_reg = gpd.read_file("datasets/data_maps/reg_estimate.gpkg")
gdf_reg["geometry"] = gdf_reg["geometry"].simplify(tolerance=100, preserve_topology=True)

gdf_prov = gpd.read_file("datasets/data_maps/prov_estimate.gpkg")
gdf_prov["geometry"] = gdf_prov["geometry"].simplify(tolerance=100, preserve_topology=True)

gdf_mun = gpd.read_file("datasets/data_maps/mun_estimate.gpkg")
gdf_mun["geometry"] = gdf_mun["geometry"].simplify(tolerance=50, preserve_topology=True)

gdf_zone = gpd.read_file("datasets/data_maps/zone_estimate.gpkg")

# ── 2. Load tabular data ─────────────────────────────────────────────────────

df = pd.read_csv("datasets/omi_estimate/omi_estimate.csv")


# ── 3. Constants & helpers ───────────────────────────────────────────────────

MAX_ZONE_PROVINCES = 3

_LEGEND_CSS = """
<style>
  .legend { color: white !important; background-color: rgba(0,0,0,0.7) !important; }
  .legend text { fill: white !important; }
</style>
"""

_PLACEHOLDER_MAP = """
<div style="display:flex;align-items:center;justify-content:center;
            height:100%;background:#111827;color:#9ca3af;font-family:sans-serif;">
  <div style="text-align:center">
    <div style="font-size:2rem;margin-bottom:.5rem">{icon}</div>
    <div>{msg}</div>
  </div>
</div>
"""

# Discover which metric columns are actually present in the geodataframes
_CANDIDATE_METRICS = ["buy_max", "buy_min", "rent_max", "rent_min"]
MAP_METRICS = [c for c in _CANDIDATE_METRICS if c in gdf_reg.columns]
if not MAP_METRICS:
    MAP_METRICS = ["buy_max"]   # safe fallback

MAP_METRIC_LABELS = {
    "buy_max":  "Max Buy Price (€/m²)",
    "buy_min":  "Min Buy Price (€/m²)",
    "rent_max": "Max Rent (€/m²)",
    "rent_min": "Min Rent (€/m²)",
}


def opts(values, placeholder: str | None = None) -> list[dict]:
    """Build Dropdown option dicts from an iterable, with an optional 'all' entry first."""
    clean = sorted({v for v in values if pd.notna(v)}, key=str)
    result = [{"label": str(v), "value": v} for v in clean]
    if placeholder:
        result = [{"label": placeholder, "value": "__all__"}] + result
    return result


def render_map(gdf: gpd.GeoDataFrame, column: str = "buy_max") -> str:
    """Return a Folium choropleth as a self-contained HTML string."""
    if gdf.empty or column not in gdf.columns:
        return _PLACEHOLDER_MAP.format(icon="🗺️", msg="No data for this selection")
    m = gdf.explore(
        tiles="CartoDB.DarkMatter",
        column=column,
        style_kwds=dict(fillOpacity=0.3, weight=0.5),
        highlight_kwds=dict(fillOpacity=0.3, weight=1, color="white"),
    )
    m.get_root().html.add_child(folium.Element(_LEGEND_CSS))
    return m.get_root().render()


def filter_df(reg=None, prov=None, mun=None, zone=None) -> pd.DataFrame:
    """Slice the tabular dataframe by geography; '__all__' means no filter."""
    f = df
    if reg  and reg  != "__all__": f = f[f["reg_name"]  == reg]
    if prov and prov != "__all__": f = f[f["prov_name"] == prov]
    if mun  and mun  != "__all__": f = f[f["mun_name"]  == mun]
    if zone and zone != "__all__": f = f[f["zone"]       == zone]
    return f


# ── 4. Layout components ─────────────────────────────────────────────────────

SCOPE_OPTIONS = [
    {"label": "🗺 Regions",        "value": "region"},
    {"label": "🏙 Provinces",      "value": "province"},
    {"label": "🏘 Municipalities", "value": "municipality"},
    {"label": "📍 Zones",          "value": "zone"},
]

# ----- Left sidebar (map controls) ------------------------------------------
sidebar = dbc.Card(
    [
        html.H6("Map Controls", className="text-uppercase text-secondary fw-bold mb-3"),

        # ── Scope ──────────────────────────────────────────────────────────
        html.Label("Geographic scope", className="small text-white fw-semibold"),
        dbc.RadioItems(
            id="scope",
            options=SCOPE_OPTIONS,
            value="region",
            className="mb-3 mt-1",
        ),
        html.Hr(className="border-secondary"),

        # ── Region filter ──────────────────────────────────────────────────
        # Visible for: municipality (required) | zone (optional pre-filter)
        html.Div(
            id="region-filter",
            children=[
                html.Label("Region", className="small text-secondary text-uppercase"),
                dcc.Dropdown(
                    id="map-region", value="__all__", clearable=False, className="dbc mb-3"
                ),
            ],
        ),

        # ── Province filter (multi, zone only) ─────────────────────────────
        html.Div(
            id="province-filter",
            children=[
                html.Label(
                    f"Province (max {MAX_ZONE_PROVINCES})",
                    className="small text-secondary text-uppercase",
                ),
                dcc.Dropdown(
                    id="map-province", value=[], multi=True, className="dbc mb-1"
                ),
                html.Small(id="province-warning", className="text-warning d-block mb-2"),
            ],
        ),

        # ── Municipality drill-down (optional, zone only) ───────────────────
        html.Div(
            id="mun-filter",
            children=[
                html.Label(
                    "Municipality (optional)",
                    className="small text-secondary text-uppercase",
                ),
                dcc.Dropdown(
                    id="map-mun",
                    value="__all__",
                    clearable=True,
                    placeholder="All municipalities",
                    className="dbc mb-3",
                ),
            ],
        ),

        html.Hr(className="border-secondary"),

        # ── Metric selector ────────────────────────────────────────────────
        html.Label("Metric", className="small text-white fw-semibold"),
        dcc.Dropdown(
            id="map-metric",
            options=[
                {"label": MAP_METRIC_LABELS.get(c, c), "value": c} for c in MAP_METRICS
            ],
            value=MAP_METRICS[0],
            clearable=False,
            className="dbc mt-1",
        ),
    ],
    body=True,
    className="bg-dark border-secondary h-100",
)

# ----- Map panel ------------------------------------------------------------
map_panel = dbc.Card(
    dcc.Loading(
        html.Iframe(
            id="map-frame",
            srcDoc=_PLACEHOLDER_MAP.format(icon="⏳", msg="Loading map…"),
            style={"width": "100%", "height": "560px", "border": "none"},
        ),
        type="circle",
        color="#375a7f",
    ),
    className="bg-dark border-secondary overflow-hidden p-0",
)

# ----- Price chart section --------------------------------------------------
chart_section = dbc.Card(
    dbc.CardBody(
        [
            html.H5("Price Trends", className="text-white mb-3"),

            # Filters row 1: geography cascade
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Region", className="small text-secondary text-uppercase"),
                            dcc.Dropdown(
                                id="chart-region",
                                options=opts(df["reg_name"].dropna().unique(), "All regions (avg)"),
                                value="__all__",
                                clearable=False,
                                className="dbc",
                            ),
                        ],
                        md=3,
                    ),
                    dbc.Col(
                        [
                            html.Label("Province", className="small text-secondary text-uppercase"),
                            dcc.Dropdown(
                                id="chart-province", value="__all__", clearable=False, className="dbc"
                            ),
                        ],
                        md=3,
                    ),
                    dbc.Col(
                        [
                            html.Label("Municipality", className="small text-secondary text-uppercase"),
                            dcc.Dropdown(
                                id="chart-mun", value="__all__", clearable=False, className="dbc"
                            ),
                        ],
                        md=3,
                    ),
                    dbc.Col(
                        [
                            html.Label("Zone", className="small text-secondary text-uppercase"),
                            dcc.Dropdown(
                                id="chart-zone", value="__all__", clearable=False, className="dbc"
                            ),
                        ],
                        md=3,
                    ),
                ],
                className="g-2 mb-2",
            ),

            # Filters row 2: property type + condition
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Property type", className="small text-secondary text-uppercase"),
                            dcc.Dropdown(
                                id="chart-type",
                                options=[
                                    {"label": t, "value": t}
                                    for t in sorted(df["type"].dropna().unique())
                                ],
                                value=sorted(df["type"].dropna().unique())[0],
                                clearable=False,
                                className="dbc",
                            ),
                        ],
                        md=3,
                    ),
                    dbc.Col(
                        [
                            html.Label("Condition", className="small text-secondary text-uppercase"),
                            dcc.Dropdown(
                                id="chart-condition", value="__all__", clearable=False, className="dbc"
                            ),
                        ],
                        md=3,
                    ),
                ],
                className="g-2 mb-3",
            ),

            dcc.Graph(id="price-chart"),
        ]
    ),
    className="bg-dark border-secondary",
)


# ── 5. App & full layout ─────────────────────────────────────────────────────

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Italian Real Estate Dashboard",
)

app.layout = dbc.Container(
    [
        # Header
        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.H3("🏠 Italian Real Estate Prices", className="text-white mb-0"),
                        html.P(
                            "Source: OMI — Osservatorio del Mercato Immobiliare",
                            className="text-secondary small mb-0",
                        ),
                    ]
                ),
                className="py-3",
            )
        ),

        # Map section (sidebar + map, side by side)
        dbc.Row(
            [
                dbc.Col(sidebar, md=3, className="mb-3"),
                dbc.Col(map_panel, md=9, className="mb-3"),
            ],
            className="align-items-stretch",
        ),

        # Chart section
        dbc.Row(dbc.Col(chart_section, className="mb-4")),
    ],
    fluid=True,
    className="px-4",
    style={"backgroundColor": "#111827", "minHeight": "100vh"},
)


# ── 6. Map callbacks ─────────────────────────────────────────────────────────

@callback(
    Output("region-filter",   "style"),
    Output("province-filter", "style"),
    Output("mun-filter",      "style"),
    Input("scope", "value"),
)
def toggle_filters(scope):
    show, hide = {"display": "block"}, {"display": "none"}
    return (
        show if scope in ("municipality", "zone") else hide,  # region filter
        show if scope == "zone" else hide,                    # province filter
        show if scope == "zone" else hide,                    # mun filter
    )


@callback(
    Output("map-region", "options"),
    Output("map-region", "value"),
    Input("scope", "value"),
)
def reset_region_opts(scope):
    placeholder = (
        "All regions (optional pre-filter)" if scope == "zone" else "Select a region…"
    )
    all_regs = opts(gdf_mun["reg_name"].dropna().unique(), placeholder)
    return all_regs, "__all__"


@callback(
    Output("map-province", "options"),
    Output("map-province", "value"),
    Input("scope",      "value"),
    Input("map-region", "value"),
)
def update_province_opts(scope, region):
    gdf = gdf_zone
    if region and region != "__all__":
        gdf = gdf[gdf["reg_name"] == region]
    return opts(gdf["prov_name"].dropna().unique()), []


@callback(
    Output("province-warning", "children"),
    Input("map-province", "value"),
)
def province_warning(provs):
    if provs and len(provs) > MAX_ZONE_PROVINCES:
        return f"⚠ Max {MAX_ZONE_PROVINCES} provinces allowed — only the first {MAX_ZONE_PROVINCES} will be shown."
    return ""


@callback(
    Output("map-mun", "options"),
    Output("map-mun", "value"),
    Input("map-province", "value"),
)
def update_mun_opts(provs):
    if not provs:
        return [], "__all__"
    selected = (provs or [])[:MAX_ZONE_PROVINCES]
    gdf = gdf_zone[gdf_zone["prov_name"].isin(selected)]
    return opts(gdf["mun_name"].dropna().unique(), "All municipalities"), "__all__"


@callback(
    Output("map-frame", "srcDoc"),
    Input("scope",        "value"),
    Input("map-region",   "value"),
    Input("map-province", "value"),
    Input("map-mun",      "value"),
    Input("map-metric",   "value"),
)
def update_map(scope, region, provinces, mun, metric):

    if scope == "region":
        return render_map(gdf_reg, metric)

    if scope == "province":
        return render_map(gdf_prov, metric)

    if scope == "municipality":
        # Require a region — rendering all ~8 000 Italian municipalities at once is too slow
        if not region or region == "__all__":
            return _PLACEHOLDER_MAP.format(
                icon="👆", msg="Select a region to view municipalities"
            )
        gdf = gdf_mun[gdf_mun["reg_name"] == region]
        return render_map(gdf, metric)

    # ── Zone scope ──────────────────────────────────────────────────────────
    selected_provs = (provinces or [])[:MAX_ZONE_PROVINCES]

    if not selected_provs:
        # Optional: show all zones in a chosen region as a starting point
        if region and region != "__all__":
            gdf = gdf_zone[gdf_zone["reg_name"] == region]
            return render_map(gdf, metric)
        return _PLACEHOLDER_MAP.format(
            icon="👆", msg="Select a region or up to 3 provinces to view zones"
        )

    gdf = gdf_zone[gdf_zone["prov_name"].isin(selected_provs)]
    if mun and mun != "__all__":
        gdf = gdf[gdf["mun_name"] == mun]

    return render_map(gdf, metric)


# ── 7. Chart callbacks ───────────────────────────────────────────────────────

@callback(
    Output("chart-province", "options"),
    Output("chart-province", "value"),
    Output("chart-province", "disabled"),
    Input("chart-region", "value"),
)
def chart_provinces(reg):
    f = filter_df(reg=reg)
    return opts(f["prov_name"].dropna().unique(), "All provinces (avg)"), "__all__", reg == "__all__"


@callback(
    Output("chart-mun", "options"),
    Output("chart-mun", "value"),
    Output("chart-mun", "disabled"),
    Input("chart-region",   "value"),
    Input("chart-province", "value"),
)
def chart_muns(reg, prov):
    f = filter_df(reg=reg, prov=prov)
    return (
        opts(f["mun_name"].dropna().unique(), "All municipalities (avg)"),
        "__all__",
        prov == "__all__",
    )


@callback(
    Output("chart-zone", "options"),
    Output("chart-zone", "value"),
    Output("chart-zone", "disabled"),
    Input("chart-region",   "value"),
    Input("chart-province", "value"),
    Input("chart-mun",      "value"),
)
def chart_zones(reg, prov, mun):
    f = filter_df(reg=reg, prov=prov, mun=mun)
    return opts(f["zone"].dropna().unique(), "All zones (avg)"), "__all__", mun == "__all__"


@callback(
    Output("chart-condition", "options"),
    Output("chart-condition", "value"),
    Input("chart-region",   "value"),
    Input("chart-province", "value"),
    Input("chart-mun",      "value"),
    Input("chart-zone",     "value"),
)
def chart_conditions(reg, prov, mun, zone):
    f = filter_df(reg=reg, prov=prov, mun=mun, zone=zone)
    return opts(f["condition"].dropna().unique(), "All conditions (avg)"), "__all__"


@callback(
    Output("price-chart", "figure"),
    Input("chart-region",    "value"),
    Input("chart-province",  "value"),
    Input("chart-mun",       "value"),
    Input("chart-zone",      "value"),
    Input("chart-type",      "value"),
    Input("chart-condition", "value"),
)
def update_chart(reg, prov, mun, zone, prop_type, condition):
    filtered = filter_df(reg=reg, prov=prov, mun=mun, zone=zone)
    filtered = filtered[filtered["type"] == prop_type]
    if condition != "__all__":
        filtered = filtered[filtered["condition"] == condition]

    plot_df = (
        filtered
        .groupby("year_semester")[["buy_min", "buy_max"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values("year_semester")
    )

    _dark = dict(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=420,
    )

    if plot_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data for the current selection",
            showarrow=False,
            font=dict(size=16, color="#9ca3af"),
        )
        fig.update_layout(**_dark)
        return fig

    x = plot_df["year_semester"].str.replace("_", " – ")

    territory = (
        mun  if mun  != "__all__" else
        prov if prov != "__all__" else
        reg  if reg  != "__all__" else
        "All Italy (avg)"
    )
    zone_lbl = f"Zone {zone}" if zone != "__all__" else "all zones"
    cond_lbl = condition      if condition != "__all__" else "all conditions"

    fig = go.Figure(
        [
            go.Scatter(
                x=x, y=plot_df["buy_max"],
                mode="lines+markers", name="Max buy price",
                line=dict(color="#f87171", width=2), marker=dict(size=4),
                hovertemplate="Max: %{y:,.0f} €/m²<extra></extra>",
            ),
            go.Scatter(
                x=x, y=plot_df["buy_min"],
                mode="lines+markers", name="Min buy price",
                line=dict(color="#60a5fa", width=2), marker=dict(size=4),
                hovertemplate="Min: %{y:,.0f} €/m²<extra></extra>",
            ),
        ]
    )
    fig.update_layout(
        title=dict(
            text=(
                f"Buy Price Trends — {territory}<br>"
                f"<sup>{prop_type} · {zone_lbl} · {cond_lbl} (avg)</sup>"
            ),
            font=dict(color="white"),
        ),
        xaxis=dict(
            title="Period", tickangle=-45, gridcolor="#374151",
            showspikes=True, spikemode="across", spikesnap="cursor",
            spikecolor="#6b7280", spikethickness=1, spikedash="dash",
        ),
        yaxis=dict(title="Price (€/m²)", gridcolor="#374151"),
        hovermode="x unified",
        hoverdistance=50,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80),
        **_dark,
    )
    return fig


# ── 8. Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)