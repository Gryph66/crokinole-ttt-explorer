# Crokinole TrueSkill Through Time Explorer

An interactive visualization tool for exploring TrueSkill Through Time (TTT) ratings of competitive crokinole players. Compare how player ratings evolve over time using **Singles-only** vs **Singles + Doubles** tournament data.

## 🎯 Live Demo

**[View the Interactive Explorer](https://Gryph66.github.io/crokinole-ttt-explorer/)**

## Features

- **Interactive Player Selection**: Choose up to 10 players to compare side-by-side
- **Dual Model Comparison**: See ratings from Singles-only and Singles+Doubles models overlaid
- **Learning Curves**: Visualize how player skill (μ) and uncertainty (σ) change over time
- **Conservative Ratings**: Display μ-3σ ratings used for official rankings
- **Rating Deltas**: See how adding doubles data affects player ratings and uncertainty
- **Responsive Design**: Works on desktop and mobile browsers

## Understanding the Visualization

- **Solid lines**: Singles-only model (μ)
- **Dashed lines**: Singles + Doubles model (μ)  
- **Shaded bands**: ±1σ uncertainty range
- **Player cards**: Show conservative ratings, ranks, and changes between models

## About TrueSkill Through Time

TrueSkill Through Time is a Bayesian skill rating system that:
- Tracks player skill evolution over time
- Handles team games (like doubles)
- Accounts for uncertainty in ratings
- Uses temporal dynamics (γ parameter) for skill drift

Model parameters used: γ=0.03, σ=1.667, β=1.0

## Data Source

Tournament results from NCA (National Crokinole Association) events.

## Regenerating the Explorer

To regenerate the HTML with updated data:

```bash
# Requires: pandas, trueskillthroughtime
pip install pandas trueskillthroughtime

# Place tournament data as nca_all_tournament_data-5.csv
python generate_ttt_explorer.py
```

## Files

- `index.html` - The interactive explorer (GitHub Pages)
- `generate_ttt_explorer.py` - Python script to regenerate the explorer
- `ftt_learningcurves.py` - Learning curve generation utilities
- `model_comparison_with_double.py` - Model comparison analysis

## License

MIT License - Feel free to use and adapt for other rating visualizations.

