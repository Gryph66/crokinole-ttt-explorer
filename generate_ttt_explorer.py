# generate_ttt_explorer.py
# Generates an interactive, self-contained HTML explorer for TrueSkill Through Time
# Compares Singles-only vs Singles+Doubles models for top 100 players

import pandas as pd
import trueskillthroughtime as ttt
import json
from datetime import datetime as dt

TOP_N = 100
GAMMA_VALUES = [0.03, 0.015, 0.0075]

# ==========================================
# 1. LOAD DATA
# ==========================================
def load_data():
    """Load tournament data from CSV."""
    print("Loading nca_all_tournament_data-5.csv...")
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
            'timestamp': date.timestamp() / (60*60*24),
            'type': event_type,
            'results': results
        })
    
    tournaments.sort(key=lambda x: x['date'])
    print(f"Loaded {len(tournaments)} tournaments")
    return tournaments

# ==========================================
# 2. TTT MODELS
# ==========================================
def run_ttt_singles_only(tournaments, gamma=0.03):
    """Run TTT using only singles matches."""
    print(f"Running TTT Singles Only (gamma={gamma})...")
    composition = []
    times = []
    for t in tournaments:
        if t['type'] != 'Singles':
            continue
        teams = [[r['player_name']] for r in t['results']]
        composition.append(teams)
        times.append(t['timestamp'])
    
    h = ttt.History(composition, times=times, gamma=gamma, sigma=1.667, beta=1.0)
    h.convergence(epsilon=1e-5, iterations=300)
    lc = h.learning_curves()
    return lc

def run_ttt_with_doubles(tournaments, gamma=0.03):
    """Run TTT using both singles and doubles matches."""
    print(f"Running TTT + Doubles (gamma={gamma})...")
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
    h.convergence(epsilon=1e-5, iterations=300)
    lc = h.learning_curves()
    return lc

def extract_learning_curve_data(lc):
    """Extract learning curve data into a serializable format."""
    data = {}
    for player, curve in lc.items():
        if curve and len(curve) >= 2:
            sorted_curve = sorted(curve, key=lambda x: x[0])
            data[player] = {
                'timestamps': [pt[0] for pt in sorted_curve],
                'dates': [dt.fromtimestamp(pt[0] * 86400).strftime('%Y-%m-%d') for pt in sorted_curve],
                'mu': [pt[1].mu for pt in sorted_curve],
                'sigma': [pt[1].sigma for pt in sorted_curve],
                'final_mu': sorted_curve[-1][1].mu,
                'final_sigma': sorted_curve[-1][1].sigma,
                'conservative': sorted_curve[-1][1].mu - 3 * sorted_curve[-1][1].sigma
            }
    return data

def get_top_players_multi_gamma(all_gamma_data, n=100):
    """Get top N players by conservative rating across all gamma values."""
    all_players = set()
    for gamma_data in all_gamma_data.values():
        all_players |= set(gamma_data['singles'].keys()) | set(gamma_data['doubles'].keys())
    
    # Use the middle gamma (0.015) as the reference for ranking
    ref_gamma = 0.015
    ref_singles = all_gamma_data[ref_gamma]['singles']
    ref_doubles = all_gamma_data[ref_gamma]['doubles']
    
    rankings = []
    for player in all_players:
        singles_con = ref_singles.get(player, {}).get('conservative', float('-inf'))
        doubles_con = ref_doubles.get(player, {}).get('conservative', float('-inf'))
        max_con = max(singles_con, doubles_con)
        rankings.append((player, max_con))
    
    rankings.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in rankings[:n]]

def generate_html(all_gamma_data, top_players, num_tournaments, num_players):
    """Generate the interactive HTML file with all gamma scenarios."""
    
    # Build player data for all gamma values
    all_player_data = {}
    for gamma in GAMMA_VALUES:
        singles_data = all_gamma_data[gamma]['singles']
        doubles_data = all_gamma_data[gamma]['doubles']
        
        player_data = {}
        for player in top_players:
            player_data[player] = {
                'singles': singles_data.get(player),
                'doubles': doubles_data.get(player),
                'singles_conservative': singles_data.get(player, {}).get('conservative'),
                'doubles_conservative': doubles_data.get(player, {}).get('conservative')
            }
        
        # Calculate ranks for this gamma
        singles_ranked = sorted(
            [(p, d['singles_conservative']) for p, d in player_data.items() if d['singles_conservative'] is not None],
            key=lambda x: x[1], reverse=True
        )
        doubles_ranked = sorted(
            [(p, d['doubles_conservative']) for p, d in player_data.items() if d['doubles_conservative'] is not None],
            key=lambda x: x[1], reverse=True
        )
        
        singles_ranks = {p: i+1 for i, (p, _) in enumerate(singles_ranked)}
        doubles_ranks = {p: i+1 for i, (p, _) in enumerate(doubles_ranked)}
        
        for player in player_data:
            player_data[player]['singles_rank'] = singles_ranks.get(player)
            player_data[player]['doubles_rank'] = doubles_ranks.get(player)
        
        all_player_data[gamma] = player_data
    
    player_list = sorted(top_players)
    
    html = generate_html_content(all_player_data, player_list, num_tournaments, num_players)
    return html

def generate_html_content(all_player_data, player_list, num_tournaments, num_players):
    import json
    
    css = """
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --bg-elevated: #30363d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --border-primary: #30363d;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-orange: #d29922;
            --accent-red: #f85149;
            --accent-purple: #a371f7;
            --accent-cyan: #39c5cf;
            --accent-pink: #db61a2;
            --accent-yellow: #e3b341;
            --shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Outfit', sans-serif; background: var(--bg-primary); color: var(--text-primary); min-height: 100vh; line-height: 1.6; }
        .header { background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-primary) 100%); border-bottom: 1px solid var(--border-primary); padding: 2rem 0; position: relative; }
        .header::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple), var(--accent-pink)); }
        .header-content { max-width: 1400px; margin: 0 auto; padding: 0 2rem; }
        h1 { font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, var(--text-primary) 0%, var(--accent-blue) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { color: var(--text-secondary); font-size: 1.1rem; }
        .container { max-width: 1400px; margin: 0 auto; padding: 2rem; }
        .controls { background: var(--bg-secondary); border: 1px solid var(--border-primary); border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: var(--shadow); }
        .controls-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 1rem; }
        .controls-title { font-size: 1rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.1em; }
        .player-selector { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; }
        .select-wrapper { position: relative; }
        select { appearance: none; background: var(--bg-tertiary); border: 1px solid var(--border-primary); border-radius: 8px; color: var(--text-primary); font-family: inherit; font-size: 0.95rem; padding: 0.75rem 2.5rem 0.75rem 1rem; cursor: pointer; min-width: 200px; }
        select:hover, select:focus { border-color: var(--accent-blue); outline: none; }
        .select-wrapper::after { content: '▼'; position: absolute; right: 12px; top: 50%; transform: translateY(-50%); color: var(--text-secondary); font-size: 0.7rem; pointer-events: none; }
        .btn { background: var(--bg-tertiary); border: 1px solid var(--border-primary); border-radius: 8px; color: var(--text-primary); font-family: inherit; font-size: 0.9rem; font-weight: 500; padding: 0.75rem 1.25rem; cursor: pointer; }
        .btn:hover { background: var(--bg-elevated); border-color: var(--accent-blue); }
        .btn-danger { color: var(--accent-red); }
        .btn-danger:hover { background: rgba(248, 81, 73, 0.1); border-color: var(--accent-red); }
        .selected-players { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem; min-height: 40px; }
        .player-tag { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; border-radius: 20px; font-size: 0.9rem; font-weight: 500; }
        .player-tag .remove { background: none; border: none; color: inherit; cursor: pointer; font-size: 1.2rem; line-height: 1; opacity: 0.7; }
        .player-tag .remove:hover { opacity: 1; }
        .chart-container { background: var(--bg-secondary); border: 1px solid var(--border-primary); border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: var(--shadow); }
        .chart-title { font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; }
        .chart-legend { display: flex; gap: 2rem; margin-bottom: 1rem; padding: 1rem; background: var(--bg-tertiary); border-radius: 8px; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; }
        .legend-line { width: 30px; height: 3px; border-radius: 2px; }
        .legend-line.solid { background: var(--text-secondary); }
        .legend-line.dashed { background: repeating-linear-gradient(90deg, var(--text-secondary) 0px, var(--text-secondary) 6px, transparent 6px, transparent 10px); }
        #chart { width: 100%; height: 600px; }
        .info-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
        .player-card { background: var(--bg-secondary); border: 1px solid var(--border-primary); border-radius: 12px; padding: 1.5rem; box-shadow: var(--shadow); }
        .player-card-header { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border-primary); }
        .player-color-dot { width: 12px; height: 12px; border-radius: 50%; }
        .player-card-name { font-size: 1.1rem; font-weight: 600; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .stat-box { background: var(--bg-tertiary); border-radius: 8px; padding: 0.75rem; }
        .stat-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
        .stat-type { font-size: 0.6rem; color: var(--text-muted); opacity: 0.8; font-style: italic; }
        .stat-value { font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 600; }
        .stat-rank { font-size: 0.85rem; color: var(--text-secondary); }
        .stat-sigma { font-size: 0.7rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; margin-top: 0.25rem; }
        .rank-change { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.85rem; padding: 0.25rem 0.5rem; border-radius: 4px; margin-top: 0.5rem; }
        .rank-up { background: rgba(63, 185, 80, 0.15); color: var(--accent-green); }
        .rank-down { background: rgba(248, 81, 73, 0.15); color: var(--accent-red); }
        .rank-same { background: rgba(139, 148, 158, 0.15); color: var(--text-secondary); }
        .deltas-row { display: flex; gap: 0.75rem; margin-top: 0.75rem; flex-wrap: wrap; }
        .delta-badge { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.75rem; padding: 0.25rem 0.5rem; border-radius: 4px; font-family: 'JetBrains Mono', monospace; }
        .delta-badge.positive { background: rgba(63, 185, 80, 0.15); color: var(--accent-green); }
        .delta-badge.negative { background: rgba(248, 81, 73, 0.15); color: var(--accent-red); }
        .delta-badge.neutral { background: rgba(139, 148, 158, 0.15); color: var(--text-secondary); }
        .delta-label { font-family: 'Outfit', sans-serif; opacity: 0.8; }
        .empty-state { text-align: center; padding: 4rem 2rem; color: var(--text-secondary); }
        .empty-state-icon { font-size: 4rem; margin-bottom: 1rem; opacity: 0.5; }
        .empty-state-text { font-size: 1.1rem; }
        .footer { text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem; border-top: 1px solid var(--border-primary); margin-top: 2rem; }
        .gamma-selector { display: flex; align-items: center; gap: 1rem; padding: 1rem; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 1rem; }
        .gamma-selector label { font-size: 0.9rem; font-weight: 500; color: var(--text-secondary); }
        .gamma-selector select { min-width: 150px; }
        .gamma-info { font-size: 0.8rem; color: var(--text-muted); margin-left: auto; }
        @media (max-width: 768px) { h1 { font-size: 1.75rem; } .container { padding: 1rem; } select { min-width: 100%; } #chart { height: 400px; } .gamma-selector { flex-direction: column; align-items: flex-start; } .gamma-info { margin-left: 0; margin-top: 0.5rem; } }
    """
    
    # Convert gamma keys to strings for JSON
    all_player_data_str_keys = {str(g): data for g, data in all_player_data.items()}
    
    js_data = f"""
        const allPlayerData = {json.dumps(all_player_data_str_keys, indent=2)};
        const playerList = {json.dumps(player_list)};
        const gammaValues = {json.dumps([str(g) for g in GAMMA_VALUES])};
        let currentGamma = "0.015";
        let playerData = allPlayerData[currentGamma];
    """
    
    js_code = """
        const colors = ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#a371f7', '#39c5cf', '#db61a2', '#e3b341', '#8b949e', '#ff7b72'];
        let selectedPlayers = [];
        
        document.addEventListener('DOMContentLoaded', function() { 
            populateDropdown(); 
            updateGammaDisplay();
        });
        
        function changeGamma(gamma) {
            currentGamma = gamma;
            playerData = allPlayerData[gamma];
            updateGammaDisplay();
            populateDropdown();
            updateUI();
        }
        
        function updateGammaDisplay() {
            document.getElementById('currentGammaValue').textContent = 'γ=' + currentGamma;
        }
        
        function populateDropdown() {
            const select = document.getElementById('playerSelect');
            const currentValue = select.value;
            select.innerHTML = '<option value="">Choose a player...</option>';
            playerList.forEach(player => {
                const option = document.createElement('option');
                option.value = player;
                const data = playerData[player];
                const rank = data?.singles_rank || data?.doubles_rank || '—';
                option.textContent = `${player} (#${rank})`;
                select.appendChild(option);
            });
            select.value = currentValue;
        }
        
        function addPlayer(name) {
            if (!name || selectedPlayers.includes(name) || selectedPlayers.length >= 10) return;
            selectedPlayers.push(name);
            document.getElementById('playerSelect').value = '';
            updateUI();
        }
        
        function removePlayer(name) {
            selectedPlayers = selectedPlayers.filter(p => p !== name);
            updateUI();
        }
        
        function clearAllPlayers() {
            selectedPlayers = [];
            updateUI();
        }
        
        function addTopPlayers(n) {
            const topPlayers = playerList
                .filter(p => playerData[p]?.singles_rank)
                .sort((a, b) => playerData[a].singles_rank - playerData[b].singles_rank)
                .slice(0, n);
            selectedPlayers = [...topPlayers];
            updateUI();
        }
        
        function addRangePlayers(start, end) {
            const rankedPlayers = playerList
                .filter(p => playerData[p]?.singles_rank)
                .sort((a, b) => playerData[a].singles_rank - playerData[b].singles_rank);
            const rangePlayers = rankedPlayers.slice(start - 1, end);
            selectedPlayers = [...rangePlayers];
            updateUI();
        }
        
        function updateUI() {
            updateTags();
            updateChart();
            updateInfoPanel();
        }
        
        function updateTags() {
            const container = document.getElementById('selectedTags');
            container.innerHTML = selectedPlayers.map((player, i) => `
                <span class="player-tag" style="background: ${colors[i]}22; color: ${colors[i]}; border: 1px solid ${colors[i]}44;">
                    <span class="player-color-dot" style="background: ${colors[i]}"></span>
                    ${player}
                    <button class="remove" onclick="removePlayer('${player}')">&times;</button>
                </span>
            `).join('');
        }
        
        function updateChart() {
            const chartDiv = document.getElementById('chart');
            if (selectedPlayers.length === 0) {
                Plotly.purge('chart');
                chartDiv.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-text">Select players above to view their skill progression</div></div>';
                return;
            }
            chartDiv.innerHTML = '';
            const traces = [];
            selectedPlayers.forEach((player, i) => {
                const data = playerData[player];
                if (!data) return;
                const color = colors[i];
                if (data.singles) {
                    const s = data.singles;
                    traces.push({x: s.dates, y: s.mu.map((m, j) => m + s.sigma[j]), mode: 'lines', line: {width: 0}, showlegend: false, hoverinfo: 'skip'});
                    traces.push({x: s.dates, y: s.mu.map((m, j) => m - s.sigma[j]), mode: 'lines', line: {width: 0}, fill: 'tonexty', fillcolor: color + '15', showlegend: false, hoverinfo: 'skip'});
                    traces.push({x: s.dates, y: s.mu, mode: 'lines', line: {color: color, width: 3}, name: `${player} (Singles)`, hovertemplate: `<b>${player}</b><br>Singles μ: %{y:.3f}<br>%{x}<extra></extra>`});
                }
                if (data.doubles) {
                    const d = data.doubles;
                    traces.push({x: d.dates, y: d.mu.map((m, j) => m + d.sigma[j]), mode: 'lines', line: {width: 0}, showlegend: false, hoverinfo: 'skip'});
                    traces.push({x: d.dates, y: d.mu.map((m, j) => m - d.sigma[j]), mode: 'lines', line: {width: 0}, fill: 'tonexty', fillcolor: color + '08', showlegend: false, hoverinfo: 'skip'});
                    traces.push({x: d.dates, y: d.mu, mode: 'lines', line: {color: color, width: 3, dash: 'dash'}, name: `${player} (+Doubles)`, hovertemplate: `<b>${player}</b><br>+Doubles μ: %{y:.3f}<br>%{x}<extra></extra>`});
                }
            });
            const layout = {paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: {family: 'Outfit, sans-serif', color: '#f0f6fc'}, margin: {l: 60, r: 30, t: 30, b: 60}, xaxis: {gridcolor: '#21262d', zerolinecolor: '#30363d'}, yaxis: {title: 'Skill Rating (μ)', gridcolor: '#21262d', zerolinecolor: '#30363d'}, legend: {orientation: 'h', y: -0.15, x: 0.5, xanchor: 'center', bgcolor: 'rgba(0,0,0,0)'}, hovermode: 'x unified', hoverlabel: {bgcolor: '#161b22', bordercolor: '#30363d'}};
            Plotly.newPlot('chart', traces, layout, {responsive: true, displayModeBar: true, modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'], displaylogo: false});
        }
        
        function updateInfoPanel() {
            const panel = document.getElementById('infoPanel');
            if (selectedPlayers.length === 0) { panel.innerHTML = ''; return; }
            panel.innerHTML = selectedPlayers.map((player, i) => {
                const data = playerData[player];
                if (!data) return '';
                const color = colors[i];
                const singlesRating = data.singles_conservative ? data.singles_conservative.toFixed(3) : '—';
                const doublesRating = data.doubles_conservative ? data.doubles_conservative.toFixed(3) : '—';
                const singlesRank = data.singles_rank || '—';
                const doublesRank = data.doubles_rank || '—';
                const singlesSigma = data.singles ? data.singles.final_sigma.toFixed(3) : '—';
                const doublesSigma = data.doubles ? data.doubles.final_sigma.toFixed(3) : '—';
                let ratingDelta = '';
                let sigmaDelta = '';
                if (data.singles_conservative && data.doubles_conservative) {
                    const rDiff = data.doubles_conservative - data.singles_conservative;
                    const rSign = rDiff >= 0 ? '+' : '';
                    const rClass = rDiff > 0.01 ? 'positive' : (rDiff < -0.01 ? 'negative' : 'neutral');
                    const rArrow = rDiff > 0.01 ? '↑' : (rDiff < -0.01 ? '↓' : '→');
                    ratingDelta = `<span class="delta-badge ${rClass}"><span class="delta-label">Δ Rating:</span> ${rArrow} ${rSign}${rDiff.toFixed(3)}</span>`;
                }
                if (data.singles && data.doubles) {
                    const sDiff = data.doubles.final_sigma - data.singles.final_sigma;
                    const sSign = sDiff >= 0 ? '+' : '';
                    const sClass = sDiff < -0.01 ? 'positive' : (sDiff > 0.01 ? 'negative' : 'neutral');
                    const sArrow = sDiff < -0.01 ? '↓' : (sDiff > 0.01 ? '↑' : '→');
                    sigmaDelta = `<span class="delta-badge ${sClass}"><span class="delta-label">Δσ:</span> ${sArrow} ${sSign}${sDiff.toFixed(3)}</span>`;
                }
                let rankChange = '';
                if (data.singles_rank && data.doubles_rank) {
                    const diff = data.singles_rank - data.doubles_rank;
                    if (diff > 0) rankChange = `<span class="rank-change rank-up">↑ ${diff} with doubles</span>`;
                    else if (diff < 0) rankChange = `<span class="rank-change rank-down">↓ ${Math.abs(diff)} with doubles</span>`;
                    else rankChange = `<span class="rank-change rank-same">— No change</span>`;
                }
                return `
                    <div class="player-card">
                        <div class="player-card-header">
                            <span class="player-color-dot" style="background: ${color}"></span>
                            <span class="player-card-name">${player}</span>
                        </div>
                        <div class="stat-grid">
                            <div class="stat-box">
                                <div class="stat-label">Singles Only</div>
                                <div class="stat-type">Conservative (μ-3σ)</div>
                                <div class="stat-value">${singlesRating}</div>
                                <div class="stat-rank">Rank #${singlesRank}</div>
                                <div class="stat-sigma">σ = ${singlesSigma}</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-label">+ Doubles</div>
                                <div class="stat-type">Conservative (μ-3σ)</div>
                                <div class="stat-value">${doublesRating}</div>
                                <div class="stat-rank">Rank #${doublesRank}</div>
                                <div class="stat-sigma">σ = ${doublesSigma}</div>
                            </div>
                        </div>
                        <div class="deltas-row">${ratingDelta}${sigmaDelta}</div>
                        ${rankChange}
                    </div>`;
            }).join('');
        }
    """
    
    gamma_options = ''.join([f'<option value="{g}" {"selected" if g == 0.015 else ""}>{g} {"(default)" if g == 0.03 else "(slower drift)" if g == 0.015 else "(slowest drift)"}</option>' for g in GAMMA_VALUES])
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crokinole TrueSkill Explorer</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>{css}</style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>🥏 Crokinole TrueSkill Explorer</h1>
            <p class="subtitle">Compare player skill progression: Singles Only vs Singles + Doubles</p>
            <p class="subtitle" style="font-size: 0.9rem; margin-top: 0.5rem;">{num_tournaments} tournaments • {num_players} players in dataset</p>
        </div>
    </header>
    <nav class="nav-bar">
        <a href="index.html" class="nav-link active">📊 Interactive Explorer</a>
        <a href="ttt_singles_vs_doubles.html" class="nav-link">📋 Rankings Table</a>
    </nav>
    <main class="container">
        <section class="controls">
            <div class="gamma-selector">
                <label for="gammaSelect">Skill Drift (γ):</label>
                <div class="select-wrapper">
                    <select id="gammaSelect" onchange="changeGamma(this.value)">
                        {gamma_options}
                    </select>
                </div>
                <span class="gamma-info">Lower γ = skills change more slowly over time • Current: <span id="currentGammaValue">γ=0.015</span></span>
            </div>
            <div class="controls-header">
                <span class="controls-title">Select Players (up to 10)</span>
                <button class="btn btn-danger" onclick="clearAllPlayers()">Clear All</button>
            </div>
            <div class="player-selector">
                <div class="select-wrapper">
                    <select id="playerSelect" onchange="addPlayer(this.value)">
                        <option value="">Choose a player...</option>
                    </select>
                </div>
                <button class="btn" onclick="addTopPlayers(5)">Add Top 5</button>
                <button class="btn" onclick="addTopPlayers(10)">Add Top 10</button>
                <button class="btn" onclick="addRangePlayers(11, 20)">Add 11-20</button>
                <button class="btn" onclick="addRangePlayers(21, 30)">Add 21-30</button>
                <button class="btn" onclick="addRangePlayers(31, 40)">Add 31-40</button>
                <button class="btn" onclick="addRangePlayers(41, 50)">Add 41-50</button>
                <button class="btn" onclick="addRangePlayers(51, 60)">Add 51-60</button>
                <button class="btn" onclick="addRangePlayers(61, 70)">Add 61-70</button>
                <button class="btn" onclick="addRangePlayers(71, 80)">Add 71-80</button>
            </div>
            <div class="selected-players" id="selectedTags"></div>
        </section>
        <section class="chart-container">
            <h2 class="chart-title">Skill Rating Over Time</h2>
            <div class="chart-legend">
                <div class="legend-item"><div class="legend-line solid"></div><span>Singles Only (μ)</span></div>
                <div class="legend-item"><div class="legend-line dashed"></div><span>Singles + Doubles (μ)</span></div>
                <div class="legend-item"><span style="color: var(--text-muted);">Shaded areas show ±1σ uncertainty</span></div>
            </div>
            <div id="chart"><div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-text">Select players above to view their skill progression</div></div></div>
        </section>
        <section class="info-panel" id="infoPanel"></section>
    </main>
    <footer class="footer">
        <p>TrueSkill Through Time Analysis • Data includes NCA tournament results</p>
        <p>Model parameters: σ=1.667, β=1.0 • γ selectable above</p>
    </footer>
    <script>{js_data}{js_code}</script>
</body>
</html>'''
    return html

def main():
    print("=" * 60)
    print("TrueSkill Through Time Interactive Explorer Generator")
    print("=" * 60)
    
    tournaments = load_data()
    
    # Run models for all gamma values
    all_gamma_data = {}
    for gamma in GAMMA_VALUES:
        print(f"\n--- Processing gamma={gamma} ---")
        singles_lc = run_ttt_singles_only(tournaments, gamma=gamma)
        doubles_lc = run_ttt_with_doubles(tournaments, gamma=gamma)
        
        singles_data = extract_learning_curve_data(singles_lc)
        doubles_data = extract_learning_curve_data(doubles_lc)
        
        print(f"  Singles model: {len(singles_data)} players")
        print(f"  Doubles model: {len(doubles_data)} players")
        
        all_gamma_data[gamma] = {
            'singles': singles_data,
            'doubles': doubles_data
        }
    
    # Get top players across all gamma values
    top_players = get_top_players_multi_gamma(all_gamma_data, TOP_N)
    print(f"\nSelected top {len(top_players)} players")
    
    print("Generating interactive HTML...")
    num_tournaments = len(tournaments)
    # Count unique players across all gammas
    all_players = set()
    for gamma_data in all_gamma_data.values():
        all_players |= set(gamma_data['singles'].keys()) | set(gamma_data['doubles'].keys())
    num_players = len(all_players)
    
    html = generate_html(all_gamma_data, top_players, num_tournaments, num_players)
    
    output_file = 'ttt_interactive_explorer.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("=" * 60)
    print(f"SUCCESS! Open '{output_file}' in any browser")
    print("=" * 60)

if __name__ == "__main__":
    main()
