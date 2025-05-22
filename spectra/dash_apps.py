# spectra/dash_apps.py
from dash import dcc, html, Dash
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from django_plotly_dash import DjangoDash

app_name = 'SimpleSpectrumPlotter' # This name must match what's in your view/template

# Create a DjangoDash app instance
dash_app = DjangoDash(name=app_name)

# Define the layout of the Dash app
dash_app.layout = html.Div([
    dcc.Graph(id='spectrum-graph'),
    # Use dcc.Store to pass initial arguments to the callback
    dcc.Store(id='initial-data-store')
])

# Define the callback to update the graph
@dash_app.callback(
    Output('spectrum-graph', 'figure'),
    [Input('initial-data-store', 'data')]
)
def update_graph(initial_data):
    # Default empty figure
    fig = go.Figure(data=[go.Scatter(x=[], y=[])], layout_title_text="Spectrum")

    if initial_data and \
       'frequency' in initial_data and \
       'intensity' in initial_data:

        frequency = initial_data.get('frequency', [])
        intensity = initial_data.get('intensity', [])
        frequency_unit = initial_data.get('frequency_unit', 'Frequency')
        intensity_unit = initial_data.get('intensity_unit', 'Intensity')
        material_name = initial_data.get('material_name', 'Spectrum Data')

        fig = go.Figure(
            data=[
                go.Scatter(x=frequency, y=intensity, mode='lines+markers')
            ],
            layout=go.Layout(
                title=f'{material_name}',
                xaxis_title=f'{frequency_unit}',
                yaxis_title=f'{intensity_unit}',
                margin=dict(l=40, r=40, t=40, b=40)
            )
        )
    return fig