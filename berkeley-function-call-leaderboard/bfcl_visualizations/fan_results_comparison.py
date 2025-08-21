#!/usr/bin/env python3
"""
Beautiful visualization of BFCL Fan Results - all interventions across categories
"""

import plotly.graph_objects as go
import plotly.io as pio
import numpy as np

# Set the default template
pio.templates.default = "plotly_white"

# Color configuration - EASY TO CHANGE!
COLOR_CONFIG = {
    'baseline': '#5B7C99',      # Muted blue-grey
    'anti_verbosity': '#7BA7BC', # Light steel blue
    'format_strict': '#A5C4D4',  # Powder blue
    'param_precision': '#B8D4E3', # Light blue
    'zero_output': '#00CED1',    # Dark turquoise - our winner!
    
    # UI colors
    'background': '#F0F8FF',     # Alice blue background
    'plot_bg': '#F5FFFE',        # Foam white plot background
    'text_primary': '#2C3E50',   # Dark blue-grey text
    'text_secondary': '#546E7A', # Blue-grey secondary text
    'accent': '#00CED1',         # Dark turquoise for links and highlights
}

def create_fan_results_comparison():
    """Create a beautiful comparison chart showing all interventions"""
    
    # Data from the report
    categories = ['simple', 'live_simple', 'live_relevance', 'irrelevance', 'live_irrelevance']
    
    # Intervention data with means and std errors
    interventions_data = {
        'Baseline': {
            'color': COLOR_CONFIG['baseline'],
            'data': [92.19, 69.52, 91.44, 68.01, 44.74],
            'errors': [0.54, 0.97, 4.23, 9.03, 9.38]
        },
        'Anti-Verbosity': {
            'color': COLOR_CONFIG['anti_verbosity'],
            'data': [90.85, 68.45, 88.22, 71.42, 52.08],
            'errors': [0.75, 1.21, 5.15, 8.21, 7.85]
        },
        'Format Strict': {
            'color': COLOR_CONFIG['format_strict'],
            'data': [90.76, 71.67, 85.12, 40.74, 41.23],
            'errors': [0.85, 1.15, 6.32, 12.15, 10.21]
        },
        'Param Precision': {
            'color': COLOR_CONFIG['param_precision'],
            'data': [89.90, 67.89, 83.45, 38.60, 40.12],
            'errors': [0.92, 1.45, 7.21, 13.42, 11.32]
        },
        'Zero Output': {
            'color': COLOR_CONFIG['zero_output'],
            'data': [92.48, 69.15, 85.67, 78.72, 58.56],
            'errors': [0.56, 1.05, 4.06, 4.21, 3.73]
        }
    }
    
    # Create figure
    fig = go.Figure()
    
    # Add bars for each intervention
    for intervention, details in interventions_data.items():
        fig.add_trace(go.Bar(
            name=intervention,
            x=categories,
            y=details['data'],
            error_y=dict(
                type='data',
                array=details['errors'],
                visible=True,
                color='rgba(0,0,0,0.5)',
                thickness=2,
                width=8
            ),
            marker_color=details['color'],
            marker_line_color='rgba(0,0,0,0.2)',
            marker_line_width=1.5,
            showlegend=True
        ))
    
    # Add key improvement annotations
    # Zero Output on live_irrelevance
    fig.add_annotation(
        x='live_irrelevance',
        y=58.56 + 3.73 + 2,
        text='<b>+13.83%</b>',
        showarrow=True,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=3,
        arrowcolor=COLOR_CONFIG['zero_output'],
        ax=0, ay=-30,
        font=dict(size=16, family="SF Pro Display, Arial", color=COLOR_CONFIG['text_primary']),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor=COLOR_CONFIG['zero_output'],
        borderwidth=2,
        borderpad=8
    )
    
    # Zero Output on irrelevance
    fig.add_annotation(
        x='irrelevance',
        y=78.72 + 4.21 + 2,
        text='<b>+10.71%</b>',
        showarrow=True,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=3,
        arrowcolor=COLOR_CONFIG['zero_output'],
        ax=0, ay=-30,
        font=dict(size=16, family="SF Pro Display, Arial", color=COLOR_CONFIG['text_primary']),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor=COLOR_CONFIG['zero_output'],
        borderwidth=2,
        borderpad=8
    )
    
    # Update layout with beautiful styling
    fig.update_layout(
        title={
            'text': 'BFCL Fan Methodology: Systematic Intervention Testing<br><sup style="font-size: 14px; color: #666;">50 trials at T=0.3 across all BFCL categories - Zero Output intervention shows dramatic improvement</sup>',
            'x': 0.5,
            'xanchor': 'center',
            'font': dict(size=24, family="SF Pro Display, Arial", color='#2F2F2F')
        },
        xaxis=dict(
            title='BFCL Category',
            titlefont=dict(size=16, family="SF Pro Display, Arial", color='#4F4F4F'),
            showgrid=False,
            showline=True,
            linewidth=2,
            linecolor='rgba(0,0,0,0.2)',
            tickfont=dict(size=14, family="SF Pro Display, Arial", color='#4F4F4F')
        ),
        yaxis=dict(
            title='Accuracy (%)',
            titlefont=dict(size=16, family="SF Pro Display, Arial", color='#4F4F4F'),
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0,0,0,0.1)',
            showline=True,
            linewidth=2,
            linecolor='rgba(0,0,0,0.2)',
            tickfont=dict(size=12, family="SF Pro Display, Arial", color='#4F4F4F'),
            range=[0, 100]
        ),
        plot_bgcolor=COLOR_CONFIG['plot_bg'],
        paper_bgcolor=COLOR_CONFIG['plot_bg'],
        height=600,
        width=1200,
        margin=dict(l=80, r=80, t=120, b=20),
        barmode='group',
        bargap=0.15,
        bargroupgap=0.1,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=14, family="SF Pro Display, Arial", color='#4F4F4F')
        )
    )
    
    return fig

def main():
    """Create visualization"""
    
    print("Creating BFCL fan results comparison...")
    
    fig = create_fan_results_comparison()
    
    # Create HTML with navigation wrapper
    html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>BFCL Fan Methodology Results - Jupiter Analysis</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: {bg_color};
        }}
        .nav-header {{
            text-align: center;
            margin-bottom: 20px;
            padding: 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .nav-header h1 {{
            margin: 0 0 10px 0;
            color: {text_color};
            font-size: 1.8em;
        }}
        .nav-header a {{
            color: #00CED1;
            text-decoration: none;
            font-weight: 600;
            font-size: 1.1em;
        }}
        .nav-header a:hover {{
            text-decoration: underline;
        }}
        #plotly-div {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div class="nav-header">
        <h1>BFCL Fan Methodology Results</h1>
        <a href="index.html">← Back to Overview</a>
    </div>
    <div style="display: flex; justify-content: center; align-items: center; min-height: calc(100vh - 200px);">
        {plot_html}
    </div>
</body>
</html>
    '''
    
    # Generate the plot HTML without the full HTML structure
    plot_html = fig.to_html(include_plotlyjs=False, div_id="plotly-div", include_mathjax=False)
    
    # Extract just the div content
    import re
    div_match = re.search(r'<div id="plotly-div".*?</script>\s*</div>', plot_html, re.DOTALL)
    if div_match:
        plot_div_content = div_match.group(0)
    else:
        plot_div_content = plot_html
    
    # Insert into template with color configuration
    full_html = html_template.format(
        plot_html=plot_div_content,
        bg_color=COLOR_CONFIG['background'],
        accent_color=COLOR_CONFIG['accent'],
        text_color=COLOR_CONFIG['text_primary']
    )
    
    # Write the file
    with open("bfcl_fan_results_comparison.html", "w") as f:
        f.write(full_html)
    
    print("✅ Created visualization:")
    print("  - bfcl_fan_results_comparison.html")

if __name__ == "__main__":
    main()