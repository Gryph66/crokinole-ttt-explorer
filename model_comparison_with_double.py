# model_comparison_with_doubles.py
import pandas as pd
import trueskillthroughtime as ttt
import plotly.graph_objects as go

# ==========================================
# 1. LOAD FULL DATA (singles + doubles)
# ==========================================
def load_data():
    print("Loading nca_all_tournament_data-6.csv (singles + doubles)...")
    df = pd.read_csv('nca_all_tournament_data-5.csv')
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
                results.append({'player_name': player, 'place': place})
                i += 1
            else:  # Doubles
                if i + 1 < len(group) and group.iloc[i + 1]['place'] == place:
                    partner = group.iloc[i + 1]['player']
                    results.append({'players': [player, partner], 'place': place})
                    i += 2
                else:
                    results.append({'players': [player], 'place': place})
                    i += 1
        
        tournaments.append({
            'id': f"{season}_{event_name}_{event_type}",
            'name': f"{event_name} ({event_type})",
            'date': date,
            'timestamp': date.timestamp() / (60*60*24),  # Days since epoch
            'type': event_type,
            'results': results
        })
    
    tournaments.sort(key=lambda x: x['date'])
    print(f"Loaded {len(tournaments)} tournaments (singles + doubles)")
    return tournaments

# ==========================================
# 2. TTT MODELS
# ==========================================
def run_ttt_singles_only(tournaments, gamma=0.03):
    composition = []
    times = []
    for t in tournaments:
        if t['type'] != 'Singles':
            continue
        teams = [[r['player_name']] for r in t['results']]
        composition.append(teams)
        times.append(t['timestamp'])
    
    h = ttt.History(composition, times=times, gamma=gamma, sigma=1.667, beta=1.0)
    h.convergence(epsilon=1e-5)
    lc = h.learning_curves()
    
    ratings = {}
    for player, curve in lc.items():
        if curve:
            final = curve[-1][1]
            ratings[player] = final.mu - 3 * final.sigma
    return ratings

def run_ttt_with_doubles(tournaments, gamma=0.03):
    composition = []
    times = []
    for t in tournaments:
        if t['type'] == 'Singles':
            teams = [[r['player_name']] for r in t['results']]
        else:
            teams = [r['players'] for r in t['results']]
        composition.append(teams)
        times.append(t['timestamp'])
    
    h = ttt.History(composition, times=times, gamma=gamma, sigma=1.667, beta=1.0)
    h.convergence(epsilon=1e-5)
    lc = h.learning_curves()
    
    ratings = {}
    for player, curve in lc.items():
        if curve:
            final = curve[-1][1]
            ratings[player] = final.mu - 3 * final.sigma
    return ratings

# ==========================================
# 3. RUN COMPARISON + GENERATE HTML
# ==========================================
def run_comparison():
    tournaments = load_data()
    
    print("Running TTT Singles Only (gamma=0.03)...")
    singles_ratings = run_ttt_singles_only(tournaments, gamma=0.03)
    
    print("Running TTT + Doubles (gamma=0.03)...")
    doubles_ratings = run_ttt_with_doubles(tournaments, gamma=0.03)
    
    # Build results DataFrame
    all_players = set(singles_ratings.keys()) | set(doubles_ratings.keys())
    data = []
    for p in all_players:
        data.append({
            'Player': p,
            'Singles_Rating': singles_ratings.get(p, float('nan')),
            'WithDoubles_Rating': doubles_ratings.get(p, float('nan'))
        })
    
    df = pd.DataFrame(data).dropna().sort_values('Singles_Rating', ascending=False).reset_index(drop=True)
    
    # Ranks
    df['Singles_Rank'] = df['Singles_Rating'].rank(ascending=False, method='min').astype(int)
    df['WithDoubles_Rank'] = df['WithDoubles_Rating'].rank(ascending=False, method='min').astype(int)
    
    # Heatmap for top 20
    top_n = 20
    top_df = df.head(top_n)
    z = [top_df['Singles_Rank'], top_df['WithDoubles_Rank']]
    text = [[f"Rank: {r}<br>Rating: {rat:.3f}" for r, rat in zip(top_df['Singles_Rank'], top_df['Singles_Rating'])],
            [f"Rank: {r}<br>Rating: {rat:.3f}" for r, rat in zip(top_df['WithDoubles_Rank'], top_df['WithDoubles_Rating'])]]
    
    fig = go.Figure(data=go.Heatmap(
        z=z, x=['Singles Only', 'With Doubles'], y=top_df['Player'],
        text=text, texttemplate="%{text}", colorscale='RdYlGn_r',
        zmin=1, zmax=50, showscale=True, colorbar=dict(title="Rank")
    ))
    fig.update_layout(title=f"TTT: Singles Only vs With Doubles – Top {top_n}", height=800, template="plotly_white")
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    # Generate clean HTML table
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>TTT Singles vs TTT + Doubles (gamma=0.03)</title>
    <style>
        body {{ font-family: sans-serif; padding: 20px; max-width: 1300px; margin: 0 auto; background: #f9f9f9; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px; text-align: center; border: 1px solid #ddd; }}
        th {{ background: #2c3e50; color: white; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .player {{ text-align: left !important; font-weight: bold; }}
        .up {{ color: green; font-weight: bold; }}
        .down {{ color: red; font-weight: bold; }}
        .chart-container {{ margin: 40px 0; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <h1>TTT Singles Only vs TTT + Doubles (gamma=0.03)</h1>
    <p>Both models use the same parameters. Doubles data adds ~50% more evidence.</p>
    
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Player</th>
                <th>Singles Only<br>Rank</th>
                <th>Rating</th>
                <th>With Doubles<br>Rank</th>
                <th>Rating</th>
                <th>Δ Rank</th>
                <th>Δ Rating</th>
            </tr>
        </thead>
        <tbody>"""
    
    for idx, row in df.head(100).iterrows():
        delta_rank = row['Singles_Rank'] - row['WithDoubles_Rank']
        delta_rating = row['WithDoubles_Rating'] - row['Singles_Rating']
        rank_class = "up" if delta_rank > 0 else "down" if delta_rank < 0 else ""
        html += f"""
            <tr>
                <td>{idx + 1}</td>
                <td class="player">{row['Player']}</td>
                <td>{row['Singles_Rank']}</td>
                <td>{row['Singles_Rating']:.3f}</td>
                <td>{row['WithDoubles_Rank']}</td>
                <td>{row['WithDoubles_Rating']:.3f}</td>
                <td class="{rank_class}">{delta_rank:+}</td>
                <td class="{rank_class}">{delta_rating:+.3f}</td>
            </tr>"""
    
    html += f"""
        </tbody>
    </table>
    
    <div class="chart-container">
        {chart_html}
    </div>
</body>
</html>"""
    
    with open('ttt_singles_vs_doubles.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("Success! Open 'ttt_singles_vs_doubles.html' to see the results.")

if __name__ == "__main__":
    run_comparison()