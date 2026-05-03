"""
Italian Real Estate Dashboard - Map Only
==========================================
Simplified version with only the interactive choropleth map visualization.

Requirements:
    pip install dash dash-bootstrap-components geopandas folium pandas

Run:
    python dashboard.py  →  http://127.0.0.1:8050
"""

import pandas as pd
import geopandas as gpd
import folium
from dash import Dash, dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc


# ── 1. Load & pre-process geodata ────────────────────────────────────────────

gdf_reg = gpd.read_file("datasets/data_maps/reg_estimate.gpkg")
gdf_reg["geometry"] = gdf_reg["geometry"].simplify(tolerance=100, preserve_topology=True)

gdf_prov = gpd.read_file("datasets/data_maps/prov_estimate.gpkg")
gdf_prov["geometry"] = gdf_prov["geometry"].simplify(tolerance=100, preserve_topology=True)

gdf_mun = gpd.read_file("datasets/data_maps/mun_estimate.gpkg")
gdf_mun["geometry"] = gdf_mun["geometry"].simplify(tolerance=50, preserve_topology=True)

gdf_zone = gpd.read_file("datasets/data_maps/zone_estimate.gpkg")


# ── 2. Constants & helpers ───────────────────────────────────────────────────

MAX_ZONE_PROVINCES = 3

_LEGEND_CSS = """
<style>
  .legend { color: white !important; background-color: rgba(0,0,0,0.7) !important; }
  .legend text { fill: white !important; }
</style>
"""

_PLACEHOLDER_MAP = """
<div style="display:flex;align-items:center;justify-content:center;
            height:100%;background:#111827;color:#9ca3af;font-family:sans-serif;font-size:14px;">
  <div style="text-align:center">
    <div style="font-size:2rem;margin-bottom:.5rem">{icon}</div>
    <div>{msg}</div>
  </div>
</div>
"""

# Discover which metric columns are present
_CANDIDATE_METRICS = ["buy_max", "buy_min", "rent_max", "rent_min"]
MAP_METRICS = [c for c in _CANDIDATE_METRICS if c in gdf_reg.columns]
if not MAP_METRICS:
    MAP_METRICS = ["buy_max"]

MAP_METRIC_LABELS = {
    "buy_max":  "Max Buy Price (€/m²)",
    "buy_min":  "Min Buy Price (€/m²)",
    "rent_max": "Max Rent (€/m²)",
    "rent_min": "Min Rent (€/m²)",
}


def render_map(gdf: gpd.GeoDataFrame, column: str = "buy_max") -> str:
    """Return a Folium choropleth as self-contained HTML."""
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


def opts(values, placeholder: str | None = None) -> list[dict]:
    """Build dropdown options."""
    clean = sorted({v for v in values if pd.notna(v)}, key=str)
    result = [{"label": str(v), "value": v} for v in clean]
    if placeholder:
        result = [{"label": placeholder, "value": "__all__"}] + result
    return result


# ── 3. App Layout ────────────────────────────────────────────────────────────

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Italian Real Estate - Map",
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
                    ],
                    className="py-3",
                )
            )
        ),

        # Controls
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Geographic Scope", className="small text-white fw-semibold mb-2"),
                        dbc.RadioItems(
                            id="scope",
                            options=[
                                {"label": " 🗺 Regions", "value": "region"},
                                {"label": " 🏙 Provinces", "value": "province"},
                                {"label": " 🏘 Municipalities", "value": "municipality"},
                                {"label": " 📍 Zones", "value": "zone"},
                            ],
                            value="region",
                            className="mb-3",
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        html.Label("Region", className="small text-white fw-semibold mb-2"),
                        dcc.Dropdown(
                            id="map-region",
                            value="__all__",
                            clearable=False,
                            className="dbc",
                        ),
                    ],
                    md=2,
                    id="region-col",
                    style={"display": "none"},
                ),
                dbc.Col(
                    [
                        html.Label("Province", className="small text-white fw-semibold mb-2"),
                        dcc.Dropdown(
                            id="map-province",
                            value=[],
                            multi=True,
                            clearable=False,
                            className="dbc",
                        ),
                        html.Small(id="province-warning", className="text-warning d-block"),
                    ],
                    md=2,
                    id="province-col",
                    style={"display": "none"},
                ),
                dbc.Col(
                    [
                        html.Label("Municipality", className="small text-white fw-semibold mb-2"),
                        dcc.Dropdown(
                            id="map-mun",
                            value="__all__",
                            clearable=True,
                            className="dbc",
                        ),
                    ],
                    md=2,
                    id="mun-col",
                    style={"display": "none"},
                ),
                dbc.Col(
                    [
                        html.Label("Metric", className="small text-white fw-semibold mb-2"),
                        dcc.Dropdown(
                            id="map-metric",
                            options=[
                                {"label": MAP_METRIC_LABELS.get(c, c), "value": c}
                                for c in MAP_METRICS
                            ],
                            value=MAP_METRICS[0],
                            clearable=False,
                            className="dbc",
                        ),
                    ],
                    md=2,
                ),
            ],
            className="mb-4 g-2",
        ),

        # Map
        dbc.Row(
            dbc.Col(
                dcc.Loading(
                    html.Iframe(
                        id="map-frame",
                        srcDoc=_PLACEHOLDER_MAP.format(icon="⏳", msg="Loading map…"),
                        style={"width": "100%", "height": "700px", "border": "none"},
                    ),
                    type="circle",
                    color="#375a7f",
                ),
                className="bg-dark border rounded p-0",
            )
        ),
    ],
    fluid=True,
    className="px-4",
    style={"backgroundColor": "#111827", "minHeight": "100vh", "paddingBottom": "2rem"},
)


# ── 4. Callbacks ─────────────────────────────────────────────────────────────

@callback(
    Output("region-col", "style"),
    Output("province-col", "style"),
    Output("mun-col", "style"),
    Input("scope", "value"),
)
def toggle_filters(scope):
    show = {"display": "block"}
    hide = {"display": "none"}
    return (
        show if scope in ("municipality", "zone") else hide,
        show if scope == "zone" else hide,
        show if scope == "zone" else hide,
    )


@callback(
    Output("map-region", "options"),
    Output("map-region", "value"),
    Input("scope", "value"),
)
def update_region_options(scope):
    placeholder = (
        "All regions (filter)" if scope == "zone" else "Select a region"
    )
    all_regs = opts(gdf_mun["reg_name"].dropna().unique(), placeholder)
    return all_regs, "__all__"


@callback(
    Output("map-province", "options"),
    Output("map-province", "value"),
    Input("scope", "value"),
    Input("map-region", "value"),
)
def update_province_options(scope, region):
    gdf = gdf_zone
    if region and region != "__all__":
        gdf = gdf[gdf["reg_name"] == region]
    return opts(gdf["prov_name"].dropna().unique()), []


@callback(
    Output("province-warning", "children"),
    Input("map-province", "value"),
)
def warn_too_many_provinces(provs):
    if provs and len(provs) > MAX_ZONE_PROVINCES:
        return f"⚠ Max {MAX_ZONE_PROVINCES} provinces — showing first {MAX_ZONE_PROVINCES}"
    return ""


@callback(
    Output("map-mun", "options"),
    Input("map-province", "value"),
)
def update_municipality_options(provs):
    if not provs:
        return []
    selected = provs[:MAX_ZONE_PROVINCES]
    gdf = gdf_zone[gdf_zone["prov_name"].isin(selected)]
    return opts(gdf["mun_name"].dropna().unique(), "All municipalities")


@callback(
    Output("map-frame", "srcDoc"),
    Input("scope", "value"),
    Input("map-region", "value"),
    Input("map-province", "value"),
    Input("map-mun", "value"),
    Input("map-metric", "value"),
)
def update_map(scope, region, provinces, mun, metric):
    if scope == "region":
        return render_map(gdf_reg, metric)

    elif scope == "province":
        return render_map(gdf_prov, metric)

    elif scope == "municipality":
        if not region or region == "__all__":
            return _PLACEHOLDER_MAP.format(
                icon="👆", msg="Select a region to view municipalities"
            )
        gdf = gdf_mun[gdf_mun["reg_name"] == region]
        return render_map(gdf, metric)

    else:  # zone
        selected_provs = (provinces or [])[:MAX_ZONE_PROVINCES]
        
        if not selected_provs:
            if region and region != "__all__":
                gdf = gdf_zone[gdf_zone["reg_name"] == region]
                return render_map(gdf, metric)
            return _PLACEHOLDER_MAP.format(
                icon="👆", msg="Select a region or provinces to view zones"
            )

        gdf = gdf_zone[gdf_zone["prov_name"].isin(selected_provs)]
        if mun and mun != "__all__":
            gdf = gdf[gdf["mun_name"] == mun]

        return render_map(gdf, metric)


# ── 5. Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)