# Hypernym Presents: BFCL Stochastic Testing & Visualization Suite

## Hypernym's Stochastic Testing Approach

### What is Stochastic Testing?

Hypernym's stochastic testing methodology for BFCL (Berkeley Function Call Leaderboard) introduces controlled randomness to evaluate the **robustness and reliability** of prompt optimization techniques across multiple runs. Unlike single-run deterministic tests that can be misleading, stochastic testing reveals the true performance distribution of models under varying conditions.

### How It Works

The stochastic testing framework (`fan_approach_stochastic_test.py`) operates by:

1. **Temperature Variation**: Running each test with `temperature=0.3` to introduce controlled randomness
2. **Multiple Iterations**: Executing 50 runs per test category to build statistical confidence
3. **Prompt Variations**: Testing multiple optimization techniques:
   - **Baseline**: Standard prompts without optimization
   - **Zero-output**: Elimination of unnecessary output tokens
   - **Anti-verbosity**: Aggressive reduction of response length
   - **Format-strict**: Enforced structured output formatting
   - **Param-precision**: Enhanced parameter type specifications
   - **Yellies**: ALL CAPS emphasis for critical instructions

4. **Statistical Collection**: Gathering distribution data including:
   - Mean performance across runs
   - Standard deviation (consistency measure)
   - Min/max bounds (worst/best case scenarios)
   - Percentile distributions (P25, P50, P75, P95)

### Data Storage & Structure

Results are stored in SQLite databases:
- **Primary**: `bfcl_stochastic_results.db` - Current test results
- **Historical**: `bfcl_results.db` - Cumulative historical data
- **Test-specific**: `fan_stochastic_results/[model_name]/` - Raw JSON outputs

**Database Schema**:
```sql
CREATE TABLE results (
    id INTEGER PRIMARY KEY,
    model TEXT,
    prompt_type TEXT,
    category TEXT,
    success_rate REAL,
    std_dev REAL,
    min_rate REAL,
    max_rate REAL,
    timestamp DATETIME
);
```

### Interpreting Stochastic Results

**Key Metrics**:
- **High Mean + Low StdDev** = Reliable improvement (best case)
- **High Mean + High StdDev** = Inconsistent improvement (risky)
- **Improvement Delta** = (Optimized Mean - Baseline Mean) 
- **Reliability Score** = Mean / (1 + StdDev) - Higher is better

**Example Interpretation**:
```
Model: Llama-4-Scout
Category: Live Irrelevance
Baseline: 29.8% ± 3.2%
Zero-output: 57.5% ± 2.1%
Improvement: +27.7% (93% relative gain)
Reliability: Increased (lower StdDev)
```

This tells us zero-output technique nearly DOUBLES performance while becoming MORE consistent.

### Visualization Pipeline

The visualization scripts transform this stochastic data into intuitive visual representations:

#### Trigger Process:
1. Run stochastic tests: `python fan_approach_stochastic_test.py`
2. Data accumulates in SQLite and JSON files
3. Visualizations read aggregated statistics
4. Generate comparative charts showing improvements

#### Output Locations:
- **Visualizations**: `bfcl_visualizations/` directory
- **Active Scripts Output**:
  - `bfcl_hypernym_jupiter_radial_dark.png` - Full radial sunburst (dark mode)
  - `bfcl_hypernym_jupiter_radial_light.png` - Full radial sunburst (light mode)
  - `bfcl_hypernym_jupiter_bow_dark.png` - Half-circle radar bow (dark mode)
  - `bfcl_hypernym_jupiter_bow_light.png` - Half-circle radar bow (light mode)

#### Visual Interpretation Guide:

**Radial Sunburst Chart**:
- **Inner rings** (darker): Baseline stochastic mean performance
- **Outer rings** (brighter): Best optimization technique performance
- **Ring height**: Performance percentage (0-100%)
- **Color coding**: Each model has unique color
- **Gap size**: Improvement magnitude

**Key Visual Insights**:
- **Uniform growth**: Technique works across all categories
- **Spiky growth**: Technique is category-specific
- **Color brightness**: Confidence level (brighter = better)
- **Annotations**: 
  - Max gain (single best improvement)
  - Average gain (overall effectiveness)

### Practical Applications

**For ML Engineers**:
- Identify which optimizations are production-ready (consistent)
- Avoid techniques with high variance (unreliable)
- Focus efforts on high-impact categories

**For Product Teams**:
- Quantify real-world performance improvements
- Make data-driven decisions on prompt engineering investments
- Demonstrate ROI of optimization efforts

**For Researchers**:
- Understand prompt sensitivity patterns
- Discover model-specific optimization strategies
- Build more robust prompting techniques

---

# BFCL Visualization Scripts

This directory contains visualization scripts for the Berkeley Function Call Leaderboard (BFCL) test results, showcasing the performance improvements achieved through Hypernym Jupiter prompt optimization techniques.

## Directory Structure

```
bfcl_visualizations/
├── scripts/                     # Visualization generation scripts
│   ├── bfcl_hypernym_jupiter_radial.py         # Main radial sunburst chart (current)
│   ├── bfcl_hypernym_jupiter_radar_bow_combined.py  # Half-radar bow chart
│   ├── bfcl_hypernym_jupiter_radar_initial.py  # Initial radar implementation
│   └── bfcl_hypernym_jupiter_radar_v3_radial_backup.py  # Backup of radial version
├── assets/                      # Static assets
│   └── hypernym_logo.png       # Hypernym logo for branding
├── bfcl_hypernym_jupiter_radial_dark.png   # Generated radial chart (dark mode)
├── bfcl_hypernym_jupiter_radial_light.png  # Generated radial chart (light mode)
├── bfcl_hypernym_jupiter_bow_dark.png      # Generated bow chart (dark mode)
└── bfcl_hypernym_jupiter_bow_light.png     # Generated bow chart (light mode)
```

## Scripts Overview

### 1. `bfcl_hypernym_jupiter_radial.py` (Main - Current Version)
**Type**: Full radial bar chart (sunburst style)
**Description**: Creates a circular "children's sun" visualization with stacked radial bars showing:
- Inner segments: Baseline performance (darker, alpha=0.3)
- Outer segments: Jupiter improvements (brighter, alpha=0.9)
- Full 360° circle with 5 models × 5 categories = 25 bars

**Features**:
- Hypernym logo integration (left of text)
- Individual letter coloring for HYPERNYM branding
- Per-model improvement statistics
- Max performance gain highlighting
- Dark and light mode support

### 2. `bfcl_hypernym_jupiter_radar_bow_combined.py`
**Type**: Half-circle radar chart (bow/arc style)
**Description**: Creates a semicircle radar visualization showing overlapping performance layers:
- Baseline performance lines (thinner, transparent)
- Jupiter-enhanced performance (thicker, opaque)
- Fill areas showing improvement zones

**Features**:
- Traditional radar chart aesthetics
- Clear before/after comparison
- Compact semicircle layout

### 3. Historical Versions
- `bfcl_hypernym_jupiter_radar_initial.py`: First implementation attempt
- `bfcl_hypernym_jupiter_radar_v3_radial_backup.py`: Backup before final adjustments

## Running the Scripts

All scripts are designed to be run from ANY directory and will:
1. Automatically find the project root
2. Locate the SQLite database
3. Load assets from `bfcl_visualizations/assets/`
4. Output to `bfcl_visualizations/`

### From Project Root
```bash
python bfcl_visualizations/scripts/bfcl_hypernym_jupiter_radial.py
```

### From Scripts Directory
```bash
cd bfcl_visualizations/scripts
python bfcl_hypernym_jupiter_radial.py
```

### From Any Directory
```bash
python /full/path/to/bfcl_visualizations/scripts/bfcl_hypernym_jupiter_radial.py
```

## Output Files

Generated visualizations are saved to `bfcl_visualizations/` with descriptive names:
- `bfcl_hypernym_jupiter_radial_dark.png` - Radial chart, dark mode
- `bfcl_hypernym_jupiter_radial_light.png` - Radial chart, light mode
- `bfcl_hypernym_jupiter_bow_dark.png` - Bow chart, dark mode
- `bfcl_hypernym_jupiter_bow_light.png` - Bow chart, light mode

## Data Source

The visualizations display performance data for 5 Llama models:
1. Meta-Llama-31-8B-Instruct-2
2. Llama-33-70B-Instruct-2
3. Meta-Llama-31-405B-Instruct (estimated)
4. Llama-4-Scout-17B-16E-Instruct
5. Llama-4-Maverick-17B-128E-Instruct-FP8

Across 5 test categories:
- Simple
- Irrelevance
- Live Irrelevance
- Live Simple
- Live Relevance

## Key Improvements Shown

The visualizations highlight:
- **Max gain**: +27.7% (Scout on Live Irrelevance)
- **Average improvement**: +10.1% across all models
- **Key techniques**:
  - Zero-output: +27% on irrelevance
  - Anti-verbosity: +24% on live tests
  - Param-precision: +5% on relevance

## Customization

### Adjusting Logo Position
In the radial script, modify `logo_offset`:
```python
logo_offset = 0.075  # Adjust this value (0.0 - 1.0)
```

### Changing Colors
Edit the `DARK_MODE` or `LIGHT_MODE` dictionaries:
```python
DARK_MODE = {
    'background': '#1a1a1f',
    'text': '#e8e6e3',
    'accent': '#f39c12',
    # ... etc
}
```

### Modifying Performance Data
Update the `MODEL_DATA` dictionary with new test results:
```python
MODEL_DATA = {
    'Meta-Llama-31-8B': {
        'baseline': [92.5, 56.0, 38.0, 70.9, 97.4],
        'best': [94.6, 80.3, 54.2, 83.1, 99.3]
    },
    # ... etc
}
```

## Dependencies

- matplotlib
- numpy
- pathlib (standard library)

Install with:
```bash
pip install matplotlib numpy
```

## Development Notes

### Coordinate Systems
- **Figure coordinates**: (0,0) = bottom-left, (1,1) = top-right of entire figure
- **Axes coordinates**: (0,0) = bottom-left, (1,1) = top-right of plot area
- Logo uses figure coordinates for absolute positioning
- Chart elements use axes coordinates for relative positioning

### Key Positioning Values (Radial)
- Hypernym logo: figure coords (0.03, 0.95)
- HYPERNYM text: figure coords (0.075, 0.95) 
- Copyright: figure coords (0.03, 0.925)
- Insights box: axes coords (-0.35, 1.0)
- Legend: axes coords (1.15, 0.5)
- Summary: axes coords (1.45, 0.3)

### Letter Kerning
HYPERNYM text uses tight kerning: 0.008 (66% of original spacing)

## Troubleshooting

**Issue**: Logo not appearing
- Check that `hypernym_logo.png` exists in `bfcl_visualizations/assets/`

**Issue**: Text overlapping
- Adjust `logo_offset` value
- Modify positioning coordinates

**Issue**: Output not saving to correct location
- Scripts automatically determine output directory
- Check console output for actual save location

## Production Logs

See `__production_steps/` for detailed development history:
- `2025_09_08_bfcl_visualization_complete_session.md` - Initial creation
- `2025_09_09_hypernym_logo_integration.md` - Logo integration

## Contact

For questions or improvements, refer to the main BFCL project documentation.