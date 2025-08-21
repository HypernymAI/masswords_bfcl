# BFCL Jupiter Report Visualizations

Interactive visualizations for the BFCL Jupiter report findings, demonstrating the systematic vulnerability detection and intervention testing methodology.

## Visualizations

### 1. Fan Results Comparison (`fan_results_comparison.py`)
Bar chart showing all 5 interventions (baseline, anti_verbosity, format_strict, param_precision, zero_output) across all 5 BFCL categories. Includes error bars from 50 trials at T=0.3. Demonstrates the systematic testing methodology.

### 2. Primary Improvements (`primary_improvements.py`)
Focused comparison of baseline vs zero_output intervention on irrelevance and live_irrelevance categories. Highlights the main findings with Cohen's d effect size annotations (1.521 and 1.936 respectively).

### 3. Behavioral Change (`behavioral_change.py`)
Simple before/after visualization showing the concrete behavioral shift: from 557.8 to 705.4 average correct empty responses per run (+26.5% improvement). Makes the impact tangible.

## Usage

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Generate All Visualizations
```bash
python generate_all_visualizations.py
```

### Generate Individual Visualizations
```bash
python fan_results_comparison.py
python primary_improvements.py
python behavioral_change.py
```

## Output Files

Each visualization generates three formats:
- `.html` - Interactive Plotly chart
- `.png` - High-resolution static image
- `.json` - Raw Plotly figure data

## Styling

Visualizations follow the llama-prompt-ops style guide:
- Clean, professional aesthetics
- SF Pro Display font family
- Consistent color schemes
- Interactive hover information
- Statistical annotations where relevant