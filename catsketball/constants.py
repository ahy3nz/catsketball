from pathlib import Path

import pandas as pd
import yaml


keep_keys = [
    'PTS', 'BLK', "STL", "REB", 'AST', 'TO', 
    'FGM', 'FGA', 'FTM', 'FTA', '3PTM'
]


def load_team_name_mapping():
    with open(
        Path(__file__).parent / "staticdata/team_id_mappings.yaml", 'r'
    ) as f:
        return yaml.safe_load(f)

def load_pro_schedule():
    temp = pd.read_csv(
        Path(__file__).parent / "staticdata/nba_schedule.csv", 
        index_col=0, parse_dates=True
    )
    return temp