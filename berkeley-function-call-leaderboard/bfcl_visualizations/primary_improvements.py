#!/usr/bin/env python3
"""
Beautiful visualization of primary improvements - focused on irrelevance categories
"""

import plotly.graph_objects as go
import plotly.io as pio
import numpy as np

# Set the default template
pio.templates.default = "plotly_white"

def create_primary_improvements():
    """Create a beautiful comparison chart with Cohen's d annotations"""
    
    # Data from the results
    methods = ['Baseline\n(Standard BFCL)', 'Zero Output\n(Jupiter Intervention)']
    
    # Data for irrelevance categories
    irrelevance_data = {
        'means': [68.01, 78.72],
        'errors': [9.03, 4.21],
        'improvement': 10.71,
        'cohen_d': 1.521
    }
    
    live_irrelevance_data = {
        'means': [44.74, 58.56],
        'errors': [9.38, 3.73],
        'improvement': 13.83,
        'cohen_d': 1.936
    }
    
    # Create figure
    fig = go.Figure()
    
    # Colors
    colors = ['#5B7C99', '#00CED1']  # Muted blue-grey and dark turquoise
    
    # Add bars for irrelevance
    for i, (method, mean, error, color) in enumerate(zip(methods, irrelevance_data['means'], 
                                                         irrelevance_data['errors'], colors)):
        fig.add_trace(go.Bar(
            x=[method],
            y=[mean],
            name='Irrelevance' if i == 0 else None,
            marker_color=color,
            marker_line_color='rgba(0,0,0,0.2)',
            marker_line_width=1.5,
            error_y=dict(
                type='data',
                array=[error],
                visible=True,
                color='rgba(0,0,0,0.5)',
                thickness=2,
                width=8
            ),
            width=0.35,
            offset=-0.2 if i == 0 else -0.2,
            showlegend=False,
            hovertemplate=f'<b>Irrelevance</b><br>{method.split(chr(10))[0]}<br>Accuracy: {mean:.2f}%<br>±{error:.2f}%<extra></extra>'
        ))
    
    # Add bars for live_irrelevance (offset to the right)
    for i, (method, mean, error, color) in enumerate(zip(methods, live_irrelevance_data['means'], 
                                                         live_irrelevance_data['errors'], colors)):
        fig.add_trace(go.Bar(
            x=[method],
            y=[mean],
            name='Live Irrelevance' if i == 0 else None,
            marker_color=color,
            marker_pattern_shape="/" if i < 2 else "",  # Add pattern to distinguish
            marker_line_color='rgba(0,0,0,0.2)',
            marker_line_width=1.5,
            error_y=dict(
                type='data',
                array=[error],
                visible=True,
                color='rgba(0,0,0,0.5)',
                thickness=2,
                width=8
            ),
            width=0.35,
            offset=0.2 if i == 0 else 0.2,
            showlegend=False,
            hovertemplate=f'<b>Live Irrelevance</b><br>{method.split(chr(10))[0]}<br>Accuracy: {mean:.2f}%<br>±{error:.2f}%<extra></extra>'
        ))
    
    # Add improvement annotations for irrelevance
    fig.add_annotation(
        x=1, y=irrelevance_data['means'][1] + irrelevance_data['errors'][1] + 3,
        text=f'<b>+{irrelevance_data["improvement"]:.2f}%</b><br><span style="font-size: 12px;">Cohen\'s d = {irrelevance_data["cohen_d"]:.3f}</span>',
        showarrow=True,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=3,
        arrowcolor='#00CED1',
        ax=-30, ay=-40,
        font=dict(size=16, family="SF Pro Display, Arial", color='#2F2F2F'),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#00CED1',
        borderwidth=2,
        borderpad=8,
        align='center'
    )
    
    # Add improvement annotations for live_irrelevance
    fig.add_annotation(
        x=1, y=live_irrelevance_data['means'][1] + live_irrelevance_data['errors'][1] + 3,
        text=f'<b>+{live_irrelevance_data["improvement"]:.2f}%</b><br><span style="font-size: 12px;">Cohen\'s d = {live_irrelevance_data["cohen_d"]:.3f}</span>',
        showarrow=True,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=3,
        arrowcolor='#00CED1',
        ax=30, ay=-40,
        font=dict(size=16, family="SF Pro Display, Arial", color='#2F2F2F'),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#00CED1',
        borderwidth=2,
        borderpad=8,
        align='center'
    )
    
    # Add critical failure annotation
    fig.add_annotation(
        x='Baseline\n(Standard BFCL)',
        y=live_irrelevance_data['means'][0] - 10,
        text='<b>44.74%</b><br>Critical restraint failure',
        showarrow=True,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=2,
        arrowcolor='#8B7355',
        ax=0, ay=40,
        font=dict(size=14, family="SF Pro Display, Arial", color='#8B7355'),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#8B7355',
        borderwidth=2,
        borderpad=6,
        align='center'
    )
    
    # Add legend manually
    fig.add_annotation(
        xref='paper', yref='paper',
        x=0.02, y=0.98,
        text='<b>Categories:</b><br>█ Solid = Irrelevance<br>▨ Pattern = Live Irrelevance',
        showarrow=False,
        font=dict(size=12, family="SF Pro Display, Arial", color='#4F4F4F'),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='rgba(0,0,0,0.2)',
        borderwidth=1,
        borderpad=8,
        align='left'
    )
    
    # Update layout with beautiful styling
    fig.update_layout(
        title={
            'text': 'Primary Finding: Dramatic Improvement in Restraint Capability<br><sup style="font-size: 14px; color: #666;">Zero Output intervention restores proper function calling restraint with large effect sizes</sup>',
            'x': 0.5,
            'xanchor': 'center',
            'font': dict(size=24, family="SF Pro Display, Arial", color='#2F2F2F')
        },
        xaxis=dict(
            showgrid=False,
            showline=False,
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
            range=[0, 85]
        ),
        plot_bgcolor='#F5FFFE',  # Foam white background
        paper_bgcolor='#F5FFFE',
        height=600,
        width=800,
        margin=dict(l=80, r=80, t=160, b=20),
        barmode='overlay'  # Overlay to show grouped pairs
    )
    
    return fig

def main():
    """Create visualization"""
    
    print("Creating primary improvements visualization...")
    
    fig = create_primary_improvements()
    
    # Create HTML with navigation wrapper
    html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Primary Improvements Analysis - Jupiter BFCL</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #F0F8FF;
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
            color: #2C3E50;
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
        <h1>Primary Improvements: Irrelevance Categories</h1>
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
    
    # Insert into template
    full_html = html_template.format(plot_html=plot_div_content)
    
    # Write the file
    with open("bfcl_primary_improvements.html", "w") as f:
        f.write(full_html)
    
    print("✅ Created visualization:")
    print("  - bfcl_primary_improvements.html")

if __name__ == "__main__":
    main()