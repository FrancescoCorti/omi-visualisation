import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, callback

# ── Load data ────────────────────────────────────────────────────────────────
df = pd.read_csv('datasets/omi_estimate/omi_estimate.csv')

# ── Helpers ──────────────────────────────────────────────────────────────────
def get_available(df, reg=None, prov=None, mun=None, zone=None):
    f = df.copy()
    if reg  and reg  != 'average': f = f[f['reg_name']  == reg]
    if prov and prov != 'average': f = f[f['prov_name'] == prov]
    if mun  and mun  != 'average': f = f[f['mun_name']  == mun]
    if zone and zone != 'average': f = f[f['zone']       == zone]
    return f

def make_options(values, all_label):
    return [{'label': all_label, 'value': 'average'}] + \
           [{'label': str(v), 'value': v} for v in sorted(values)]

# ── App layout ───────────────────────────────────────────────────────────────
app = Dash(__name__)

app.layout = html.Div([
    html.Div([
        html.Div([
            html.Label('Region'),
            dcc.Dropdown(
                id='dd-region',
                options=make_options(df['reg_name'].dropna().unique(), 'Average (all regions)'),
                value='average', clearable=False
            ),
        ], style={'width': '24%'}),
        html.Div([
            html.Label('Province'),
            dcc.Dropdown(id='dd-province', value='average', clearable=False),
        ], style={'width': '24%'}),
        html.Div([
            html.Label('Municipality'),
            dcc.Dropdown(id='dd-mun', value='average', clearable=False),
        ], style={'width': '24%'}),
        html.Div([
            html.Label('Zone'),
            dcc.Dropdown(id='dd-zone', value='average', clearable=False),
        ], style={'width': '24%'}),
    ], style={'display': 'flex', 'gap': '12px', 'marginBottom': '12px'}),

    html.Div([
        html.Div([
            html.Label('Property type'),
            dcc.Dropdown(
                id='dd-type',
                options=[{'label': t, 'value': t} for t in sorted(df['type'].dropna().unique())],
                value='Residential housing', clearable=False
            ),
        ], style={'width': '24%'}),
        html.Div([
            html.Label('Condition'),
            dcc.Dropdown(id='dd-condition', value='average', clearable=False),
        ], style={'width': '24%'}),
    ], style={'display': 'flex', 'gap': '12px', 'marginBottom': '24px'}),

    dcc.Graph(id='price-chart'),
], style={'padding': '24px', 'fontFamily': 'sans-serif'})

# ── Cascade: update province options ─────────────────────────────────────────
@callback(
    Output('dd-province', 'options'),
    Output('dd-province', 'value'),
    Output('dd-province', 'disabled'),
    Input('dd-region', 'value'),
)
def update_province(reg):
    f = get_available(df, reg=reg)
    opts = make_options(f['prov_name'].dropna().unique(), 'Average (all provinces)')
    return opts, 'average', (reg == 'average')

# ── Cascade: update municipality options ─────────────────────────────────────
@callback(
    Output('dd-mun', 'options'),
    Output('dd-mun', 'value'),
    Output('dd-mun', 'disabled'),
    Input('dd-region', 'value'),
    Input('dd-province', 'value'),
)
def update_mun(reg, prov):
    f = get_available(df, reg=reg, prov=prov)
    opts = make_options(f['mun_name'].dropna().unique(), 'Average (all municipalities)')
    return opts, 'average', (prov == 'average')

# ── Cascade: update zone options ──────────────────────────────────────────────
@callback(
    Output('dd-zone', 'options'),
    Output('dd-zone', 'value'),
    Output('dd-zone', 'disabled'),
    Input('dd-region', 'value'),
    Input('dd-province', 'value'),
    Input('dd-mun', 'value'),
)
def update_zone(reg, prov, mun):
    f = get_available(df, reg=reg, prov=prov, mun=mun)
    opts = make_options(f['zone'].dropna().unique(), 'Average (all zones)')
    return opts, 'average', (mun == 'average')

# ── Cascade: update condition options ────────────────────────────────────────
@callback(
    Output('dd-condition', 'options'),
    Output('dd-condition', 'value'),
    Input('dd-region', 'value'),
    Input('dd-province', 'value'),
    Input('dd-mun', 'value'),
    Input('dd-zone', 'value'),
)
def update_condition(reg, prov, mun, zone):
    f = get_available(df, reg=reg, prov=prov, mun=mun, zone=zone)
    opts = make_options(f['condition'].dropna().unique(), 'Average (all conditions)')
    return opts, 'average'

# ── Main chart callback ───────────────────────────────────────────────────────
@callback(
    Output('price-chart', 'figure'),
    Input('dd-region',    'value'),
    Input('dd-province',  'value'),
    Input('dd-mun',       'value'),
    Input('dd-zone',      'value'),
    Input('dd-type',      'value'),
    Input('dd-condition', 'value'),
)
def update_chart(reg, prov, mun, zone, prop_type, condition):
    filtered = get_available(df, reg=reg, prov=prov, mun=mun, zone=zone)
    filtered = filtered[filtered['type'] == prop_type]
    if condition != 'average':
        filtered = filtered[filtered['condition'] == condition]

    plot_df = (
        filtered
        .groupby('year_semester')[['buy_min', 'buy_max']]
        .mean()
        .reset_index()
        .sort_values('year_semester')
    )

    plot_df['buy_mean'] = (plot_df['buy_max'] + plot_df['buy_min'])/2

    if plot_df.empty:
        return go.Figure().add_annotation(text="No data for current selection",
                                          showarrow=False, font_size=16)

    x = plot_df['year_semester'].str.replace('_', ' - ')
    territory = mun if mun != 'average' else prov if prov != 'average' else \
                reg if reg != 'average' else 'All regions (avg)'
    zone_label = f'Zone: {zone}' if zone != 'average' else 'All zones (avg)'
    cond_label = condition.capitalize() if condition != 'average' else 'All conditions (avg)'
    subtitle = f'{prop_type} · {territory} · {zone_label} · {cond_label}'

    fig = go.Figure([
        go.Scatter(x=x, y=plot_df['buy_max'], mode='lines', name='buy_max',
                   line=dict(color='tomato', width=2),
                   hovertemplate='Max. buying price: %{y:,.0f}<extra></extra>'),
        go.Scatter(x=x, y=plot_df['buy_mean'], mode='lines', name='buy_mean',
                   line=dict(color='springgreen', width=2),
                   hovertemplate='Mean. buying price: %{y:,.0f}<extra></extra>'),
        go.Scatter(x=x, y=plot_df['buy_min'], mode='lines', name='buy_min',
                   line=dict(color='steelblue', width=2),
                   hovertemplate='Min. buying price: %{y:,.0f}<extra></extra>'),
    ])
    fig.update_layout(
        title=dict(text=f'Buy Price Trends<br><sup>{subtitle}</sup>'),
        xaxis=dict(title='Year - Semester', tickangle=-45,
                   showspikes=True, spikemode='across', spikesnap='cursor',
                   spikecolor='grey', spikethickness=1, spikedash='dash'),
        yaxis=dict(title='Price (€/m²)'),
        hovermode='x unified', hoverdistance=50, spikedistance=50,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white', height=500,
    )
    return fig

# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)