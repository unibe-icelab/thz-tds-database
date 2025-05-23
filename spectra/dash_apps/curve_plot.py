import urllib

from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output, State, ALL
import plotly.graph_objs as go
from spectra.models import Spectrum
import dash

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = DjangoDash("CurvePlot", external_stylesheets=external_stylesheets)
measurements = Spectrum.objects.all()

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="dummy-output"),
    html.Div([
        # Sidebar
        html.Div([
            html.H3("Measurements", style={'marginBottom': '8px', 'color': '#1a2d46', 'fontSize': '18px'}),
            dcc.Input(
                id="search-input",
                type="text",
                placeholder="Search...",
                style={"width": "95%", "marginBottom": "8px", "fontSize": "14px"}
            ),
            html.Div(
                id="measurement-list",
                children=[
                    html.Button(
                        m.material.name,
                        id={'type': 'measurement-btn', 'index': m.id},
                        n_clicks=0,
                        style={'width': '100%', 'textAlign': 'left', 'margin': '2px 0', 'fontSize': '14px'}
                    ) for m in measurements
                ],
                style={
                    'flex': '1',
                    'border': '1px solid #ccc',
                    'background': '#f9f9f9',
                    'padding': '0 4px',
                    'minHeight': 0,
                    'boxSizing': 'border-box'
                }
            )
        ], style={
            'width': '260px',
            'minWidth': '180px',
            'maxWidth': '320px',
            'padding': '12px 8px 12px 12px',
            'borderRight': '2px solid #ddd',
            'boxSizing': 'border-box',
            'height': '100%',
            'background': '#f4f6fa',
            'display': 'flex',
            'flexDirection': 'column',
            'flex': '0 0 260px'
        }),

        # Plot area
        html.Div([
            dcc.Graph(
                id="measurement-graph-refidx",
                animate=True,
                style={
                    "backgroundColor": "#1a2d46",
                    'color': '#ffffff',
                    'height': '38vh',
                    'borderRadius': '8px',
                    'boxShadow': '0 2px 8px rgba(0,0,0,0.10)',
                    'marginBottom': '8px',
                    'width': '100%'
                }
            ),
            dcc.Graph(
                id="measurement-graph-abscoeff",
                animate=True,
                style={
                    "backgroundColor": "#1a2d46",
                    'color': '#ffffff',
                    'height': '38vh',
                    'borderRadius': '8px',
                    'boxShadow': '0 2px 8px rgba(0,0,0,0.10)',
                    'width': '100%'
                }
            )
        ], style={
            'flex': '1',
            'padding': '16px 16px 16px 16px',
            'display': 'flex',
            'flexDirection': 'column',
            'alignItems': 'stretch',
            'justifyContent': 'flex-start',
            'background': '#1a2d46',
            'height': '100%',
            'boxSizing': 'border-box'
        }),
    ], style={
        'display': 'flex',
        'flexDirection': 'row',
        'width': '100%',
        'height': '100%',
        'background': '#1a2d46',
        'margin': '0',
        'padding': '0',
        'boxSizing': 'border-box'
    })
], style={
    'background': '#1a2d46',
    'height': '100%',
    'width': '100%',
    'margin': '0',
    'padding': '0',
    'boxSizing': 'border-box'
})


app.clientside_callback(
    """
    function(n_clicks_list, ids) {
        if (!n_clicks_list || !ids) { return window.dash_clientside.no_update; }
        for (let i = 0; i < n_clicks_list.length; i++) {
            if (n_clicks_list[i]) {
                const id = ids[i].index;
                window.location.href = `/spectra/curveplot/?spectrum_id=${id}`;
                break;
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("dummy-output", "children"),
    Input({'type': 'measurement-btn', 'index': ALL}, 'n_clicks'),
    State({'type': 'measurement-btn', 'index': ALL}, 'id'),
    prevent_initial_call=True
)

@app.callback(
    Output("url", "search"),
    Input({'type': 'measurement-btn', 'index': ALL}, 'n_clicks'),
    State({'type': 'measurement-btn', 'index': ALL}, 'id'),
    prevent_initial_call=True
)
def update_url(n_clicks_list, ids):
    # Find the first button with n_clicks > 0
    for n_clicks, id_dict in zip(n_clicks_list, ids):
        if n_clicks and id_dict is not None:
            return f"?spectrum_id={id_dict['index']}"
    return dash.no_update

@app.callback(
    Output("measurement-list", "children"),
    Input("search-input", "value")
)
def update_measurement_list(search):
    query = Spectrum.objects.all()
    if search:
        query = query.filter(material__name__icontains=search)

    return [
        html.Button(
            m.material.name,
            id={'type': 'measurement-btn', 'index': m.id},
            n_clicks=0,
            style={'width': '100%', 'margin': '2px 0', 'textAlign': 'left', 'fontSize': '14px'}
        ) for m in query
    ]

@app.callback(
    Output("your-plot", "figure"),
    Input("url", "search"),
)
def update_plot(search):
    print("updating plooooot")
    if not search:
        return empty_figure()  # or dash.no_update

    query = parse_qs(search.lstrip("?"))
    spectrum_id = query.get("spectrum_id", [None])[0]
    if not spectrum_id:
        return empty_figure()

    # Load spectrum data from your data source
    spectrum = load_spectrum(spectrum_id)
    if not spectrum:
        return empty_figure()

    return plot_figure(spectrum)

@app.callback(
    Output("measurement-graph-refidx", "figure"),
    Output("measurement-graph-abscoeff", "figure"),
    Input("url", "search"),
    prevent_initial_call=False
)
def update_plots_from_url(search):
    import plotly.graph_objs as go
    from spectra.models import Spectrum

    axis_style = dict(showgrid=False, showline=True, linecolor='white', linewidth=2, zeroline=False)
    empty_layout = dict(
        paper_bgcolor='#1a2d46',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        xaxis=axis_style,
        yaxis=axis_style
    )
    spectrum_id = None
    if search:
        params = urllib.parse.parse_qs(search.lstrip('?'))
        spectrum_id = params.get('spectrum_id', [None])[0]
    if not spectrum_id:
        return go.Figure(layout=empty_layout), go.Figure(layout=empty_layout)
    try:
        m = Spectrum.objects.get(id=spectrum_id)
    except Spectrum.DoesNotExist:
        return go.Figure(layout=empty_layout), go.Figure(layout=empty_layout)
    freq = getattr(m, 'frequency_data', [])
    refidx = getattr(m, 'refractive_index_data', [])
    abscoeff = getattr(m, 'absorption_coefficient_data', [])

    fig_refidx = go.Figure()
    if freq and refidx:
        fig_refidx.add_trace(go.Scatter(x=freq, y=refidx, mode='lines', name=m.material.name))
        fig_refidx.update_layout(
            title="Refractive Index",
            xaxis_title="Frequency",
            yaxis_title="Refractive Index (n)",
            xaxis=axis_style,
            yaxis=axis_style,
            paper_bgcolor='#1a2d46',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
    else:
        fig_refidx.update_layout(title="No refractive index data", **empty_layout)

    fig_abscoeff = go.Figure()
    if freq and abscoeff:
        fig_abscoeff.add_trace(go.Scatter(x=freq, y=abscoeff, mode='lines', name=m.material.name))
        fig_abscoeff.update_layout(
            title="Absorption Coefficient",
            xaxis_title="Frequency",
            yaxis_title="Absorption Coefficient",
            xaxis=axis_style,
            yaxis=axis_style,
            paper_bgcolor='#1a2d46',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
    else:
        fig_abscoeff.update_layout(title="No absorption coefficient data", **empty_layout)

    return fig_refidx, fig_abscoeff