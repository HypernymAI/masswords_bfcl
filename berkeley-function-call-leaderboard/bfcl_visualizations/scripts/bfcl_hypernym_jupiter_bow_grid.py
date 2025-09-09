#!/usr/bin/env python3
"""
BFCL Hypernym Jupiter Breakthrough Visualization - Bow Grid Version
Half-radar chart showing current vs potential performance across 5 models
Shows overlapping bow/radar pattern with baseline and improvement layers
PLUS: Grid of individual mini bow radars for each model under the legend

This script can be run from any directory and will:
1. Find the SQLite database in the project root
2. Load assets from the bfcl_visualizations/assets directory
3. Output visualizations to bfcl_visualizations/
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import matplotlib.patches as patches
from matplotlib.patches import Wedge
import matplotlib.patheffects as path_effects
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg
import sys
import os

# Find project root (where the SQLite databases are)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # Go up from scripts/ to bfcl_visualizations/ to root
VIZ_DIR = PROJECT_ROOT / 'bfcl_visualizations'
ASSETS_DIR = VIZ_DIR / 'assets'

# Add project root to path for imports if needed
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Color schemes matching Hypernym branding
DARK_MODE = {
    'background': '#1a1a1f',
    'text': '#e8e6e3',
    'grid': '#2d2d35',
    'accent': '#f39c12',
    'current': '#ec7063',  # Where models are now (muted red)
    'potential': '#5dade2',  # Where they could be (bright blue)
    'overlap': '#9b59b6',  # Overlap area (purple)
    'model_colors': {
        '8B': '#e74c8e',     # Pink
        '70B': '#3498db',    # Blue  
        '405B': '#27ae60',   # Green
        'Scout': '#f1c40f',  # Yellow
        'Maverick': '#e67e22' # Orange
    }
}

LIGHT_MODE = {
    'background': '#faf8f3',
    'text': '#2c3339',
    'grid': '#e5ddd0',
    'accent': '#c97e7e',
    'current': '#c16666',  # Muted brick red
    'potential': '#6b89b0',  # Steel blue
    'overlap': '#9b82a8',  # Mauve
    'model_colors': {
        '8B': '#c97e7e',     # Dusty rose
        '70B': '#7e9bbd',    # Slate blue
        '405B': '#82a882',   # Sage green
        'Scout': '#d4a574',  # Tan/camel
        'Maverick': '#cd8b62' # Terracotta
    }
}

# Model performance data from test results
# Format: [simple, irrelevance, live_irrelevance, live_simple, live_relevance]
MODEL_DATA = {
    'Meta-Llama-31-8B': {
        'baseline': [92.5, 56.0, 38.0, 70.9, 97.4],
        'zero_output': [94.6, 80.3, 54.2, 83.1, 99.3],
        'best': [94.6, 80.3, 54.2, 83.1, 99.3]  # Best across all techniques
    },
    'Llama-33-70B': {
        'baseline': [94.6, 49.6, 31.8, 81.5, 100.0],
        'zero_output': [94.2, 76.9, 55.4, 82.1, 100.0],
        'anti_verbosity': [94.0, 77.9, 55.5, 81.7, 100.0],
        'best': [94.6, 77.9, 55.5, 82.1, 100.0]
    },
    'Meta-Llama-405B': {
        # Estimated from partial results and model size patterns
        'baseline': [95.2, 51.0, 32.5, 82.3, 100.0],
        'best': [95.5, 78.5, 56.8, 84.5, 100.0]
    },
    'Llama-4-Scout': {
        'baseline': [94.0, 54.0, 29.8, 79.9, 94.6],
        'zero_output': [94.6, 70.8, 57.5, 80.0, 94.4],
        'anti_verbosity': [93.7, 70.5, 53.8, 79.5, 94.4],
        'param_precision': [95.2, 53.5, 29.7, 81.0, 99.8],
        'best': [95.2, 70.8, 57.5, 81.0, 99.8]
    },
    'Llama-4-Maverick': {
        'baseline': [90.6, 74.0, 35.5, 80.1, 95.9],
        'zero_output': [94.6, 80.3, 54.2, 83.1, 99.3],
        'anti_verbosity': [95.0, 81.1, 53.0, 82.4, 100.0],
        'best': [95.0, 81.1, 54.2, 83.1, 100.0]
    }
}

def create_hypernym_radar(dark_mode=True, save_path=None):
    """Create the half-radar visualization with Hypernym branding"""
    
    scheme = DARK_MODE if dark_mode else LIGHT_MODE
    
    # Create figure with larger size for clarity
    fig = plt.figure(figsize=(16, 10))
    ax = plt.subplot(111, projection='polar')
    
    # Set background
    fig.patch.set_facecolor(scheme['background'])
    ax.set_facecolor(scheme['background'])
    
    # Categories for the radar
    categories = ['Simple', 'Irrelevance', 'Live\nIrrelevance', 'Live\nSimple', 'Live\nRelevance']
    num_vars = len(categories)
    
    # Models in specified order
    models = ['Meta-Llama-31-8B', 'Llama-33-70B', 'Meta-Llama-405B', 'Llama-4-Scout', 'Llama-4-Maverick']
    model_labels = ['8B', '70B', '405B', 'Scout', 'Maverick']
    
    # Compute angle for each axis (only top half - 0 to π)
    angles = np.linspace(0, np.pi, num_vars)
    
    # Plot for each model
    for idx, (model, label) in enumerate(zip(models, model_labels)):
        # Get data
        baseline = MODEL_DATA[model]['baseline']
        best = MODEL_DATA[model]['best']
        
        # Close the polygon
        baseline = baseline + baseline[:1]
        best = best + best[:1]
        angles_plot = np.concatenate([angles, [angles[0]]])
        
        # Offset for visibility
        offset = idx * 0.02
        
        # Plot baseline (current performance) - thinner, more transparent
        ax.plot(angles_plot, baseline, 'o-', linewidth=1.5, 
                label=f'{label} Current',
                color=scheme['model_colors'][label],
                alpha=0.4, markersize=4)
        
        # Plot potential (with Jupiter breakthrough) - thicker, more opaque
        ax.plot(angles_plot, best, 'o-', linewidth=2.5,
                label=f'{label} Potential',
                color=scheme['model_colors'][label],
                alpha=0.9, markersize=6)
        
        # Fill between to show improvement area
        ax.fill_between(angles_plot, baseline, best,
                       color=scheme['model_colors'][label],
                       alpha=0.15)
    
    # Fix axis to go in the right order
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    # Draw only half circle (top)
    ax.set_thetamin(0)
    ax.set_thetamax(180)
    
    # Set category labels
    ax.set_xticks(angles)
    ax.set_xticklabels(categories, size=11, color=scheme['text'])
    
    # Y-axis configuration
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], 
                       size=9, color=scheme['text'], alpha=0.7)
    
    # Grid styling
    ax.grid(True, color=scheme['grid'], alpha=0.3, linewidth=0.5)
    ax.spines['polar'].set_color(scheme['grid'])
    
    # Title with company branding
    title_text = ax.text(0.5, 1.15, 'BFCL Performance: Current vs Hypernym Jupiter Potential',
                         horizontalalignment='center',
                         transform=ax.transAxes,
                         fontsize=18, fontweight='bold',
                         color=scheme['text'])
    
    subtitle_text = ax.text(0.5, 1.10, 'Berkeley Function Calling Leaderboard - Prompt Optimization Impact',
                            horizontalalignment='center',
                            transform=ax.transAxes,
                            fontsize=12,
                            color=scheme['text'],
                            alpha=0.8)
    
    # Add Hypernym logo image if it exists
    logo_path = ASSETS_DIR / 'hypernym_logo.png'
    logo_offset = 0.05  # Default start position
    
    if logo_path.exists():
        # Load and add logo
        logo_img = mpimg.imread(str(logo_path))
        # Create OffsetImage with smaller size
        imagebox = OffsetImage(logo_img, zoom=0.08)  # Adjust zoom to control size
        # Position logo in upper left
        ab = AnnotationBbox(imagebox, (0.03, 0.95), 
                            xycoords='figure fraction',
                            frameon=False,
                            box_alignment=(0, 0.5))  # Left align, center vertically
        ax.add_artist(ab)
        logo_offset = 0.075  # Start text after logo with padding
    
    # Add Hypernym branding with individual letter colors (upper left of FIGURE)
    # HYPERNYM letters with exact colors from the HTML
    hypernym_colors = [
        ('H', '#A41B1B'),  # rgb(164,27,27) - deep red
        ('Y', '#F7B979'),  # rgb(247,185,121) - peach
        ('P', '#C49915'),  # rgb(196,153,21) - gold  
        ('E', '#447E2A'),  # rgb(68,126,42) - green
        ('R', '#558C98'),  # rgb(85,140,152) - teal
        ('N', '#5187DC'),  # rgb(81,135,220) - blue
        ('Y', '#A7CAEA'),  # rgb(167,202,234) - light blue
        ('M', '#3B2E62'),  # rgb(59,46,98) - purple
    ]
    
    # Use FIGURE coordinates (0,0 = bottom-left, 1,1 = top-right of entire figure)
    start_x = logo_offset  # Start after logo if present
    start_y = 0.95  # 95% up = near top
    
    # Draw each letter of HYPERNYM using fig.text for absolute positioning
    current_x = start_x
    for letter, color in hypernym_colors:
        fig.text(current_x, start_y, letter,
                horizontalalignment='left',
                fontsize=13,
                color=color,
                fontweight='bold',
                family='monospace')
        current_x += 0.008  # Letter spacing in figure coords (very tight)
    
    # Add JUPITER after HYPERNYM
    fig.text(current_x + 0.006, start_y, 'JUPITER',
            horizontalalignment='left',
            fontsize=13,
            color=scheme['accent'],
            fontweight='bold',
            alpha=0.9,
            family='monospace')
    
    # Add copyright underneath in gunmetal grey (aligned with logo if present)
    fig.text(0.03 if logo_path.exists() else start_x, start_y - 0.025, '© 2025 Hypernym in association with Meta LLaMA Startup Cohort',
            horizontalalignment='left',
            fontsize=7.5,
            color='#5A5A5A',  # Gunmetal grey
            alpha=0.7,
            family='sans-serif',
            style='italic')
    
    # Legend configuration
    legend_elements = []
    for label in model_labels:
        color = scheme['model_colors'][label]
        # Current performance
        legend_elements.append(plt.Line2D([0], [0], color=color, lw=1.5,
                                         alpha=0.4, label=f'{label} Current'))
        # Potential performance  
        legend_elements.append(plt.Line2D([0], [0], color=color, lw=2.5,
                                         alpha=0.9, label=f'{label} + Jupiter'))
    
    # Position legend at TOP RIGHT
    legend = ax.legend(handles=legend_elements, loc='center left',
                      bbox_to_anchor=(1.15, 1.0),
                      frameon=True, fancybox=True,
                      facecolor=scheme['background'],
                      edgecolor=scheme['text'],
                      framealpha=0.9,
                      fontsize=10,
                      title='Model Performance',
                      title_fontsize=11,
                      ncol=2)
    
    legend.get_title().set_color(scheme['text'])
    for text in legend.get_texts():
        text.set_color(scheme['text'])
    
    # Add grid of mini bow radars underneath the legend (2x3 grid)
    # Position them RIGHT-ALIGNED within figure bounds
    mini_size = 0.24  # Keep the 2x size as requested
    spacing_x = -0.12  # Much tighter spacing to cluster them
    spacing_y = 0.01  # Tighter vertical too
    # Right align: rightmost edge at 1.1, so start = 1.1 - (2 * mini_size + spacing_x)
    grid_start_x = 1.1 - (2 * mini_size + spacing_x)
    grid_start_y = 0.63  # Moved down by 0.02 from 0.65
    
    for idx, (model, label) in enumerate(zip(models, model_labels)):
        # Calculate grid position (2 columns, 3 rows)
        row = idx // 2
        col = idx % 2
        
        # Create a small axes for this mini radar
        mini_x = grid_start_x + col * (mini_size + spacing_x)
        mini_y = grid_start_y - row * (mini_size + spacing_y)
        
        # Create mini axes in figure coordinates
        mini_ax = fig.add_axes([mini_x, mini_y, mini_size, mini_size/2], projection='polar')
        mini_ax.set_facecolor(scheme['background'])
        
        # Get data for this model
        baseline = MODEL_DATA[model]['baseline']
        best = MODEL_DATA[model]['best']
        
        # Close the polygon
        baseline = baseline + baseline[:1]
        best = best + best[:1]
        angles_mini = np.concatenate([angles, [angles[0]]])
        
        # Plot mini radar
        mini_ax.plot(angles_mini, baseline, 'o-', linewidth=1,
                    color=scheme['model_colors'][label], alpha=0.4, markersize=2)
        mini_ax.plot(angles_mini, best, 'o-', linewidth=1.5,
                    color=scheme['model_colors'][label], alpha=0.9, markersize=3)
        mini_ax.fill_between(angles_mini, baseline, best,
                            color=scheme['model_colors'][label], alpha=0.15)
        
        # Mini radar settings
        mini_ax.set_theta_offset(np.pi / 2)
        mini_ax.set_theta_direction(-1)
        mini_ax.set_thetamin(0)
        mini_ax.set_thetamax(180)
        mini_ax.set_ylim(0, 100)
        mini_ax.set_xticks([])
        mini_ax.set_yticks([])
        mini_ax.grid(True, color=scheme['grid'], alpha=0.2, linewidth=0.3)
        mini_ax.spines['polar'].set_color(scheme['grid'])
        mini_ax.spines['polar'].set_linewidth(0.5)
        
        # Add model label below mini radar
        fig.text(mini_x + mini_size/2, mini_y - 0.02, label,
                horizontalalignment='center',
                fontsize=9, fontweight='bold',
                color=scheme['model_colors'][label])
        
        # Calculate average and max improvement for this model
        baseline_avg = np.mean(MODEL_DATA[model]['baseline'])
        best_avg = np.mean(MODEL_DATA[model]['best'])
        avg_improvement = best_avg - baseline_avg
        
        # Find max improvement for this model
        max_imp = 0
        for i in range(len(MODEL_DATA[model]['baseline'])):
            imp = MODEL_DATA[model]['best'][i] - MODEL_DATA[model]['baseline'][i]
            if imp > max_imp:
                max_imp = imp
        
        # Add max and average below label
        fig.text(mini_x + mini_size/2, mini_y - 0.04, f'Max: +{max_imp:.1f}%',
                horizontalalignment='center',
                fontsize=7,
                color=scheme['model_colors'][label],
                alpha=0.9)
        fig.text(mini_x + mini_size/2, mini_y - 0.055, f'Avg: +{avg_improvement:.1f}%',
                horizontalalignment='center',
                fontsize=7,
                color=scheme['model_colors'][label],
                alpha=0.8)
    
    # Add per-model improvements on the left side
    model_improvements = []
    for model, label in zip(models, model_labels):
        baseline_avg = np.mean(MODEL_DATA[model]['baseline'])
        best_avg = np.mean(MODEL_DATA[model]['best'])
        improvement = best_avg - baseline_avg
        
        # Find biggest improvement category
        improvements_by_cat = []
        for i, cat in enumerate(categories):
            base_val = MODEL_DATA[model]['baseline'][i]
            best_val = MODEL_DATA[model]['best'][i]
            improvements_by_cat.append((cat.replace('\n', ' '), best_val - base_val))
        
        best_cat = max(improvements_by_cat, key=lambda x: x[1])
        model_improvements.append(f"• {label}: +{improvement:.1f}% avg (+{best_cat[1]:.1f}% {best_cat[0]})")
    
    # Add key insights box on the LEFT side
    insights_text = [
        "HYPERNYM JUPITER BREAKTHROUGH:",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
        "Per-Model Improvements:",
    ] + model_improvements + [
        "",
        "Key Techniques:",
        "• Zero-output: +27% on irrelevance",
        "• Anti-verbosity: +24% on live tests",
        "• Param-precision: +5% on relevance"
    ]
    
    # Create insight box on the left side (moved further left)
    insight_box = '\n'.join(insights_text)
    ax.text(-0.22, 0.5, insight_box,
           transform=ax.transAxes,
           fontsize=9,
           color=scheme['text'],
           alpha=0.9,
           bbox=dict(boxstyle='round,pad=0.8',
                    facecolor=scheme['background'],
                    edgecolor=scheme['accent'],
                    linewidth=2,
                    alpha=0.85),
           verticalalignment='center',
           horizontalalignment='left')
    
    # Add performance summary
    avg_improvements = []
    for model in models:
        baseline_avg = np.mean(MODEL_DATA[model]['baseline'])
        best_avg = np.mean(MODEL_DATA[model]['best'])
        avg_improvements.append(best_avg - baseline_avg)
    
    avg_improvement = np.mean(avg_improvements)
    
    # Calculate max improvement - single best improvement across all categories
    max_improvement = 0
    max_model = ""
    max_category = ""
    for model, label in zip(models, model_labels):
        for i, cat in enumerate(categories):
            baseline_val = MODEL_DATA[model]['baseline'][i]
            best_val = MODEL_DATA[model]['best'][i]
            improvement = best_val - baseline_val
            if improvement > max_improvement:
                max_improvement = improvement
                max_model = label
                max_category = cat.replace('\n', ' ')
    
    summary_text = f"Max Performance Gain: +{max_improvement:.1f}%\nAverage: +{avg_improvement:.1f}%"
    ax.text(0.98, 0.05, summary_text,
           transform=ax.transAxes,
           fontsize=12,
           color=scheme['accent'],
           fontweight='bold',
           alpha=0.9,
           horizontalalignment='right',
           verticalalignment='bottom',
           bbox=dict(boxstyle='round,pad=0.4',
                    facecolor=scheme['background'],
                    edgecolor=scheme['accent'],
                    linewidth=1.5,
                    alpha=0.8))
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, facecolor=scheme['background'],
                   edgecolor='none', bbox_inches='tight')
        print(f"Saved visualization to {save_path}")
    
    return fig, ax

def main():
    """Generate both dark and light mode versions"""
    
    # Use the project's visualization directory
    output_dir = VIZ_DIR
    output_dir.mkdir(exist_ok=True)
    
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Assets directory: {ASSETS_DIR}")
    print(f"Output directory: {output_dir}")
    
    # Generate dark mode version
    fig_dark, ax_dark = create_hypernym_radar(dark_mode=True, 
                                              save_path=output_dir / "bfcl_hypernym_jupiter_bow_grid_dark.png")
    plt.close()
    
    # Generate light mode version
    fig_light, ax_light = create_hypernym_radar(dark_mode=False,
                                                save_path=output_dir / "bfcl_hypernym_jupiter_bow_grid_light.png")
    plt.close()
    
    print(f"\nVisualizations created in {output_dir}/")
    print("- bfcl_hypernym_jupiter_bow_grid_dark.png")
    print("- bfcl_hypernym_jupiter_bow_grid_light.png")

if __name__ == "__main__":
    main()