# crokinole_topN_FINAL_HIGH_CONTRAST_WORKING.py
# Top N players — maximum contrast, fully interactive, NO ERRORS

import pandas as pd
import trueskillthroughtime as ttt
import plotly.graph_objects as go
from datetime import datetime as dt

TOP_N = 20  # ← Change to 10, 20, 30, 50, 100 — works perfectly!

def load_data():
    df = pd.read_csv('nca_all_tournament_data-6.csv')
    df['date'] = pd.to_datetime(df['tournament_date'])
    tournaments = []
    grouped = df.groupby(['season', 'event', 'date', 'type'])
    
    for (season, event_name, date, event_type), group in grouped:
        group = group.sort_values('place')
        results = []
        i = 0
        while i < len(group):
            row = group.iloc[i]
            player = row['player']
            place = row['place']
            if event_type == 'Singles':
                results.append({'player_name': player})
                i += 1
            else:
                if i + 1 < len(group) and group.iloc[i + 1]['place'] == place:
                    partner = group.iloc[i + 1]['player']
                    results.append({'players': [player, partner]})
                    i += 2
                else:
                    results.append({'players': [player]})
                    i += 1
        
        tournaments.append({
            'timestamp': date.timestamp() / (60*60*24),
            'type': event_type,
            'results': results
        })
    
    tournaments.sort(key=lambda x: x['timestamp'])
    return tournaments

def run_ttt():
    tournaments = load_data()
    composition = []
    times = []
    for t in tournaments:
        teams = [[r['player_name']] if t['type'] == 'Singles' else r['players'] for r in t['results']]
        composition.append(teams)
        times.append(t['timestamp'])
    
    print(f"Running TTT + Doubles (gamma=0.03) for Top {TOP_N}...")
    h = ttt.History(composition, times=times, gamma=0.03, sigma=1.667, beta=1.0)
    h.convergence(epsilon=1e-6, iterations=300)
    lc = h.learning_curves()
    return lc

lc = run_ttt()

# Final conservative ratings
final_con = {}
for player, curve in lc.items():
    if curve:
        final = curve[-1][1]
        final_con[player] = final.mu - 3 * final.sigma

# Top N by conservative rating
top_players = sorted(final_con.items(), key=lambda x: x[1], reverse=True)[:TOP_N]
top_names = [name for name, _ in top_players]

# HIGH-CONTRAST ColorBrewer Dark2 palette (8 bold colors)
dark2_hex = [
    '#1b9e77', '#d95f02', '#7570b3', '#e7298a',
    '#66a61e', '#e6ab02', '#a6761d', '#666666'
]

fig = go.Figure()

for i, player in enumerate(top_names):
    if player not in lc or len(lc[player]) < 2:
        continue
        
    curve = sorted(lc[player], key=lambda x: x[0])
    dates = [dt.fromtimestamp(t * 86400) for t in [pt[0] for pt in curve]]
    mu = [pt[1].mu for pt in curve]
    sigma = [pt[1].sigma for pt in curve]
    final_rating = final_con[player]
    
    color_hex = dark2_hex[i % len(dark2_hex)]
    
    # Convert hex to RGB
    r = int(color_hex[1:3], 16)
    g = int(color_hex[3:5], 16)
    b = int(color_hex[5:7], 16)
    
    rgba_fill = f"rgba({r},{g},{b},0.25)"
    rgb_line = f"rgb({r},{g},{b})"

    # Upper band
    fig.add_trace(go.Scatter(
        x=dates, y=[m + s for m, s in zip(mu, sigma)],
        mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    
    # Lower band + fill
    fig.add_trace(go.Scatter(
        x=dates, y=[m - s for m, s in zip(mu, sigma)],
        mode='lines', line=dict(width=0),
        fill='tonexty',
        fillcolor=rgba_fill,
        showlegend=False, hoverinfo='skip'
    ))
    
    # Mean line — bold
    fig.add_trace(go.Scatter(
        x=dates, y=mu,
        mode='lines',
        line=dict(color=rgb_line, width=5),
        name=f"{player} → {final_rating:.3f}"
    ))

fig.update_layout(
    title=f"<b>Crokinole Top {TOP_N} — TrueSkill Through Time + Doubles</b><br>"
          "Mean skill with light uncertainty bands (ranked by conservative rating)",
    xaxis_title="Time",
    yaxis_title="Estimated Skill (μ ± σ)",
    hovermode="x unified",
    legend=dict(x=1.02, y=1, font=dict(size=12)),
    template="plotly_white",
    height=900,
    width=1600
)

fig.write_html(f'crokinole_top{TOP_N}_FINAL_HIGH_CONTRAST.html')
print(f"SUCCESS → crokinole_top{TOP_N}_FINAL_HIGH_CONTRAST.html")