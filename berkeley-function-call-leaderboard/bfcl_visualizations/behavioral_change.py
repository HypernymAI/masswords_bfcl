#!/usr/bin/env python3
"""
Beautiful visualization of behavioral change - empty response improvement
"""

import plotly.graph_objects as go
import plotly.io as pio
import numpy as np

# Set the default template
pio.templates.default = "plotly_white"

def create_behavioral_change():
    """Create a beautiful before/after comparison"""
    
    # Data from the report
    methods = ['Baseline\n(Explains Instead)', 'Zero Output\n(Proper Restraint)']
    total_values = [557.8, 705.4]
    
    # Breakdown data
    irrelevance_values = [163.2, 188.9]
    live_irrelevance_values = [394.6, 516.5]
    
    # Create figure
    fig = go.Figure()
    
    # Add irrelevance portion
    fig.add_trace(go.Bar(
        name='Irrelevance',
        x=methods,
        y=irrelevance_values,
        marker_color='#B0E0E6',  # Powder blue
        marker_line_color='rgba(0,0,0,0.2)',
        marker_line_width=1.5,
        hovertemplate='<b>Irrelevance</b><br>Count: %{y:.1f}<extra></extra>',
        showlegend=True
    ))
    
    # Add live_irrelevance portion
    fig.add_trace(go.Bar(
        name='Live Irrelevance',
        x=methods,
        y=live_irrelevance_values,
        marker_color='#4682B4',  # Steel blue
        marker_line_color='rgba(0,0,0,0.2)',
        marker_line_width=1.5,
        hovertemplate='<b>Live Irrelevance</b><br>Count: %{y:.1f}<extra></extra>',
        showlegend=True
    ))
    
    # Add total value annotations
    for i, (method, total) in enumerate(zip(methods, total_values)):
        color = '#5B7C99' if i == 0 else '#00CED1'  # Muted blue-grey for baseline, turquoise for improved
        fig.add_annotation(
            x=method,
            y=total + 20,
            text=f'<b>{total:.1f}</b>',
            showarrow=False,
            font=dict(size=28, family="SF Pro Display, Arial", color=color)
        )
    
    # Add improvement annotation
    improvement = total_values[1] - total_values[0]
    percentage = (improvement / total_values[0]) * 100
    fig.add_annotation(
        x=1, y=total_values[1] - 50,
        text=f'<b>+{improvement:.1f}</b><br><span style="font-size: 14px;">(+{percentage:.1f}%)</span>',
        showarrow=True,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=3,
        arrowcolor='#00CED1',
        ax=-70, ay=40,
        font=dict(size=20, family="SF Pro Display, Arial", color='#2F2F2F'),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#00CED1',
        borderwidth=2,
        borderpad=8,
        align='center'
    )
    
    # Add transformation arrow between bars
    fig.add_annotation(
        x=0.5,
        y=400,
        text='→',
        showarrow=False,
        font=dict(size=60, family="Arial", color='#20B2AA'),
        xref='paper',
        yref='y'
    )
    
    # Add explanatory text
    fig.add_annotation(
        xref='paper', yref='paper',
        x=0.02, y=0.5,
        text='<b>Key Finding</b><br><br>The zero_output<br>intervention enables<br>proper restraint:<br><br>Models correctly<br>output [] when<br>no functions apply',
        showarrow=False,
        font=dict(size=14, family="SF Pro Display, Arial", color='#4F4F4F'),
        bgcolor='rgba(224,255,255,0.8)',
        bordercolor='#00CED1',
        borderwidth=2,
        borderpad=10,
        align='left'
    )
    
    # Update layout with beautiful styling
    fig.update_layout(
        title={
            'text': 'Behavioral Change: Correct Empty Response Generation<br><sup style="font-size: 14px; color: #666;">Average correct empty responses [] per 50-trial run</sup>',
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
            title='Number of Correct Empty Responses',
            titlefont=dict(size=16, family="SF Pro Display, Arial", color='#4F4F4F'),
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0,0,0,0.1)',
            showline=True,
            linewidth=2,
            linecolor='rgba(0,0,0,0.2)',
            tickfont=dict(size=12, family="SF Pro Display, Arial", color='#4F4F4F'),
            range=[0, 800]
        ),
        plot_bgcolor='#F5FFFE',  # Foam white background
        paper_bgcolor='#F5FFFE',
        height=600,
        width=900,
        margin=dict(l=80, r=80, t=120, b=20),
        barmode='stack',
        legend=dict(
            x=0.98,
            y=0.98,
            xanchor='right',
            yanchor='top',
            font=dict(size=14, family="SF Pro Display, Arial", color='#4F4F4F'),
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='rgba(0,0,0,0.2)',
            borderwidth=1
        )
    )
    
    return fig

def main():
    """Create visualization"""
    
    print("Creating behavioral change visualization...")
    
    fig = create_behavioral_change()
    
    # Create HTML with navigation wrapper
    html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Behavioral Change Analysis - Jupiter BFCL</title>
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
        <h1>Behavioral Change: Empty Response Generation</h1>
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
    with open("bfcl_behavioral_change.html", "w") as f:
        f.write(full_html)
    
    print("✅ Created visualization:")
    print("  - bfcl_behavioral_change.html")

if __name__ == "__main__":
    main()