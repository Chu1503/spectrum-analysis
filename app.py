import os
import pandas as pd
import plotly.graph_objects as go
import dash
from dash import Dash, dcc, html, Input, Output, State, ALL
from flask import Flask

server = Flask(__name__)
app = Dash(__name__, server=server)

cases = {
    "Blank": {
        "file": "data/t-white-blank.txt",
        "color": "black",
        "description": "Blank"
    },
    "Case 1": {
        "file": "data/t-1white.txt",
        "color": "red",
        "description": "10µL FITC-BSA with 290µL water"
    },
    "Case 2": {
        "file": "data/t-2white.txt",
        "color": "green",
        "description": "20µL FITC-BSA with 280µL water"
    },
    "Case 3": {
        "file": "data/t-3white.txt",
        "color": "blue",
        "description": "30µL FITC-BSA with 270µL water"
    },
    "Case 4": {
        "file": "data/t-4white.txt",
        "color": "orange",
        "description": "50µL FITC-BSA with 250µL water"
    },
}

def load_spectra(file_path):
    try:
        data = pd.read_csv(file_path, sep=r'\s+', header=None, 
                         names=['nm', 'percentage'], engine='python')
        data = data.apply(pd.to_numeric, errors='coerce').dropna()
        return data
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

app.layout = html.Div([
    dcc.Graph(id='spectra-plot'),
    dcc.Checklist(
        id='case-selector',
        options=[{'label': k, 'value': k} for k in cases.keys()],
        value=['Blank'],
        inline=True
    ),
    html.Div(id='controls-container')
])

def create_controls(case_key):
    case = cases[case_key]
    return html.Div([
        html.H4(f"{case['description']}", 
               style={'color': case['color']}),
        html.Div([
            html.Div([
                html.Label("Cursor 1"),
                dcc.Input(
                    id={'type': 'cursor-input', 'case': case_key, 'cursor': 1},
                    type='number', min=450, max=700, step=0.1, value=462.7,
                    style={'width': '100px', 'margin-left': '10px'}
                ),
                dcc.Slider(
                    min=450, max=700, step=0.1, value=462.7,
                    marks={i: str(i) for i in range(450, 700, 50)},
                    id={'type': 'cursor-slider', 'case': case_key, 'cursor': 1}
                )
            ], style={'margin-bottom': '20px'}),
            
            html.Div([
                html.Label("Cursor 2"),
                dcc.Input(
                    id={'type': 'cursor-input', 'case': case_key, 'cursor': 2},
                    type='number', min=450, max=700, step=0.1, value=560,
                    style={'width': '100px', 'margin-left': '10px'}
                ),
                dcc.Slider(
                    min=450, max=700, step=0.1, value=560,
                    marks={i: str(i) for i in range(450, 700, 50)},
                    id={'type': 'cursor-slider', 'case': case_key, 'cursor': 2}
                )
            ], style={'margin-bottom': '20px'}),
            
            html.Div(id={'type': 'diff-output', 'case': case_key},
                    style={'color': case['color'], 'fontWeight': 'bold'})
        ]),
        html.Hr()
    ])

@app.callback(
    Output('controls-container', 'children'),
    Input('case-selector', 'value')
)
def update_controls(selected_cases):
    return [create_controls(case) for case in selected_cases]

@app.callback(
    Output({'type': 'cursor-slider', 'case': ALL, 'cursor': ALL}, 'value'),
    Output({'type': 'cursor-input', 'case': ALL, 'cursor': ALL}, 'value'),
    Input({'type': 'cursor-slider', 'case': ALL, 'cursor': ALL}, 'value'),
    Input({'type': 'cursor-input', 'case': ALL, 'cursor': ALL}, 'value'),
    Input('spectra-plot', 'clickData')
)
def sync_inputs(slider_values, input_values, click_data):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'] if ctx.triggered else None

    if 'spectra-plot.clickData' in trigger_id:
        # Update cursor positions based on click
        clicked_wavelength = click_data['points'][0]['x']
        updated_values = [clicked_wavelength] * len(slider_values)
        return updated_values, updated_values
    else:
        # Sync sliders and inputs
        updated_values = input_values if 'cursor-input' in str(trigger_id) else slider_values
        return updated_values, updated_values

@app.callback(
    [Output('spectra-plot', 'figure'),
     Output({'type': 'diff-output', 'case': ALL}, 'children')],
    Input({'type': 'cursor-slider', 'case': ALL, 'cursor': ALL}, 'value'),
    State('case-selector', 'value')
)
def update_plot(slider_values, selected_cases):
    fig = go.Figure()
    diff_outputs = []
    cursor_map = {}

    for i, case_key in enumerate(selected_cases):
        cursor_start = i * 2
        cursor_map[case_key] = {
            1: slider_values[cursor_start],
            2: slider_values[cursor_start + 1]
        }

    for case_key in selected_cases:
        case = cases.get(case_key)
        if not case:
            continue
            
        data = load_spectra(case['file'])
        if data is None or data.empty:
            continue

        # Add main trace
        fig.add_trace(go.Scatter(
            x=data['nm'], 
            y=data['percentage'], 
            mode='lines',
            line=dict(color=case['color']),
            name=case['description']
        ))

        # Get cursor positions
        cursor1 = cursor_map[case_key][1]
        cursor2 = cursor_map[case_key][2]
        
        # Calculate intensity values
        idx1 = (data['nm'] - cursor1).abs().idxmin()
        idx2 = (data['nm'] - cursor2).abs().idxmin()
        i1 = data.iloc[idx1]['percentage']
        i2 = data.iloc[idx2]['percentage']

        # Add cursors to plot
        fig.add_shape(type="line", x0=cursor1, x1=cursor1, 
                     y0=0, y1=data['percentage'].max(),
                     line=dict(color=case['color'], dash="dash"))
        fig.add_shape(type="line", x0=cursor2, x1=cursor2,
                     y0=0, y1=data['percentage'].max(),
                     line=dict(color=case['color'], dash="dash"))
        
        # Add annotations for cursor wavelengths
        fig.add_annotation(
            x=cursor1, y=data['percentage'].max(),
            text=f"{cursor1:.2f} nm",
            showarrow=False,
            yshift=10,
            font=dict(color=case['color'])
        )
        fig.add_annotation(
            x=cursor2, y=data['percentage'].max(),
            text=f"{cursor2:.2f} nm",
            showarrow=False,
            yshift=10,
            font=dict(color=case['color'])
        )
        
        # Create delta output
        diff_output = f"Δλ = {abs(cursor2 - cursor1):.2f} nm, ΔI = {abs(i2 - i1):.2f}%"
        diff_outputs.append(diff_output)

    fig.update_layout(
        title="Fluorescence Spectrum Analysis",
        xaxis_title="Wavelength (nm)",
        yaxis_title="Intensity (%)",
        hovermode="closest",
        template="plotly_white"
    )
    
    return fig, diff_outputs

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)