from pathlib import Path
from src.pipeline.orchestrator import _load_truth
from src.graders.grade_match import grade_match

truth = _load_truth(Path('data/snapshots/bayern_madrid_ucl_qf_l2/truth.json'))
# minimal prediction (deliberately low quality)
pred = {
    'win_probs': {'home': 0.5, 'draw': 0.3, 'away': 0.2},
    'score_dist': [{'score': '2-1', 'p': 0.4}, {'score': '1-0', 'p': 0.6}],
    'most_likely_score': '2-1',
    'expected_goal_diff': 1.0,
    'lineups': {
        'home': {'starting': [{'name': n, 'position': 'M'} for n in
            ['M. Neuer','J. Stanisic','D. Upamecano','J. Tah','K. Laimer',
             'J. Kimmich','A. Pavlovic','M. Olise','S. Gnabry','L. Diaz','H. Kane']],
                 'bench': []},
        'away': {'starting': [{'name': 'A. Lunin', 'position': 'G'}]*11, 'bench': []},
    },
    'formations': {'home': '4-2-3-1', 'away': '4-3-3'},
    'scorers': [{'player': 'H. Kane', 'team': 'home', 'p': 0.5, 'minute_range': [35, 45]}],
    'assisters': [],
    'substitutions': [{'team': 'home', 'off': 'J. Stanisic', 'on': 'A. Davies', 'minute': 46}],
    'cards': [],
    'penalties': [],
    'own_goals': [],
    'motm_probs': [{'player': 'H. Kane', 'p': 0.4}],
    'stats': {
        'possession': {'home': 65, 'away': 35},
        'shots': {'home': 18, 'away': 10},
        'shots_on_target': {'home': 7, 'away': 4},
        'corners': {'home': 7, 'away': 3},
        'pass_accuracy': {'home': 85, 'away': 75},
        'fouls': {'home': 12, 'away': 14},
        'saves': {'home': 3, 'away': 6},
        'defensive_actions': {'home': 25, 'away': 20},
    },
    'reasoning': {'overall': 'x' * 80, 't1_result': 'r', 't2_player': 'r', 't3_events': 'r', 't4_stats': 'r'},
}
result = grade_match(pred, truth)
print('composite:', round(result['composite'], 1))
print('layers:', {k: round(v, 1) for k, v in result['layers'].items()})
errors = {t: v for t, v in result['tasks'].items() if isinstance(v, dict) and v.get('error')}
print('task errors:', errors)

# with open("data/predictions/1534911/test.json", "w") as f:
#     import json
#     json.dump(pred, f, ensure_ascii=False, indent=4)