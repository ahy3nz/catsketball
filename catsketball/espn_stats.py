from collections import defaultdict
import datetime
import json
from typing import Dict, List, Optional
import pandas as pd
import streamlit as st
import warnings
from espn_api.basketball import Player, League, Team

import constants


def get_num_games(
    schedule: pd.DataFrame, 
    team_id: int, 
    start_date: datetime.datetime, 
    end_date: datetime.datetime
):
    """ Find number of games for a particular NBA team
    
    start_date <= date_range < end_date """
    date_filter = (
        (start_date <= schedule.index) &
        (schedule.index < end_date)
    )
    num_games = (
        schedule
        .loc[
            date_filter, 
            str(team_id)
        ].sum(skipna=True)
    )

    return num_games


def get_avg_stats_player(player: Player, include_dtdq=False, include_o=False):
    """ Pull stats for partiucular player
    Stats prefaced with '00' are actual, observed stats
    Stats prefaced with '10' are predicted stats for that season
    
    Lots of different ways to estimate stats for players,
    naively average the different estimates to get the
    average stats for a particular player.
    
    This function is the most error-prone as it depends on how ESPN
    choose to organize its player stats each season
    """
    # Ignore player if on IR
    # If a player is injured but NOT on IR, still factor his stats
    stat_estimates = []
    if (
        (player.lineupSlot == "IR") or 
        (_is_out(player) and not include_o) or 
        (_is_dtdq(player) and not include_dtdq)
    ):
        return defaultdict(int)
    if '2024' in player.stats:
        if 'avg' in player.stats['2024']:
            stat_estimates.append(player.stats['2024']['avg'])
    if '2024_projected' in player.stats:
        if 'avg' in player.stats['2024_projected']:
            stat_estimates.append(player.stats['2024_projected']['avg'])
    if '2024_last_30' in player.stats:
        if 'avg' in player.stats['2024_last_30']:
            stat_estimates.append(player.stats['2024_last_30']['avg'])
    if len(stat_estimates) == 0:
        warnings.warn(f"Can't find stats for player {player}")
        return defaultdict(int)
    stats_to_add = (
        pd.DataFrame(
            stat_estimates,
            index=range(len(stat_estimates))
        )
        .mean()
        .to_dict()
    )
    if 'FG%' not in stats_to_add:
        if stats_to_add.get('FGA', 0) == 0:
            stats_to_add['FG%'] = 0
        else:
            stats_to_add['FG%'] = stats_to_add['FGM'] / stats_to_add['FGA']
        
    if 'FT%' not in stats_to_add:
        if stats_to_add.get('FTA', 0) == 0:
            stats_to_add['FT%'] = 0 
        else:
            stats_to_add['FT%'] = stats_to_add['FTM'] / stats_to_add['FTA']
    return stats_to_add


def get_weekly_stats_player(
    player: Player, 
    start_date: datetime.datetime, 
    end_date: datetime.datetime, 
    team_id_name_mapping: Optional[dict] = None, 
    schedule: Optional[pd.DataFrame] = None,
    include_dtdq=False,
    include_o=False
):
    """ Given a time range, predict categories"""
    if team_id_name_mapping is None:
        team_id_name_mapping = constants.load_team_name_mapping()
    if schedule is None:
        schedule = constants.load_pro_schedule()
        
    team_id = team_id_name_mapping[player.proTeam.upper()]
    num_games = get_num_games(schedule, team_id, start_date, end_date)
    player_avg_stats = get_avg_stats_player(player, include_dtdq=include_dtdq, include_o=include_o)
    # Ignore player if injured or IR
    if (
        (player.lineupSlot=="IR") or
        (_is_out(player) and not include_o) or
        (_is_dtdq(player) and not include_dtdq)
    ):
        relevant_stats = {
            k: 0
            for k in constants.keep_keys
        }
        relevant_stats['FG%'] = 0
        relevant_stats['FT%'] = 0
    
    else:
        relevant_stats = {
            k: num_games * player_avg_stats.get(k, 0)
            for k in constants.keep_keys
        }
        relevant_stats['FG%'] = (
            relevant_stats['FGM'] / relevant_stats['FGA']
        )
        relevant_stats['FT%'] = (
            relevant_stats['FTM'] / relevant_stats['FTA']    
        )
    relevant_stats['Name'] = player.name
    
    return relevant_stats


def get_avg_stats_roster(
    team_roster: List[Player], 
    include_dtdq=False, 
    include_o=False
):
    """ For a fantasy team, get per-game-averaged stats 
    for each player """
    all_records = []
    for player in team_roster:
        player_stats = get_avg_stats_player(
            player, include_dtdq=include_dtdq, include_o=include_o
        )
        player_stats['Name'] = player.name
        all_records.append(player_stats)
        
    return (
        pd.DataFrame(all_records)
        .set_index("Name")
        .fillna(0.0)
    )


def get_weekly_stats_roster(
    team: Team, 
    start_date: datetime.datetime, 
    end_date: datetime.datetime,
    include_dtdq=False,
    include_o=False
):
    """ For a fantasy team, project categories for roster """
    all_records = []
    for player in team.roster:
        entry = get_weekly_stats_player(
            player, start_date, end_date, include_dtdq=include_dtdq, 
            include_o=include_o
        )
        entry['Name'] = player.name
        all_records.append(entry)
        
    return pd.DataFrame(all_records).set_index("Name").fillna(0.0)


def get_avg_stats_team(team: Team, include_dtdq=False, include_o=False):
    """ Get average stats for an entire team"""
    to_return = reduce_roster_stats_to_team(
        get_avg_stats_roster(
            team.roster, 
            include_dtdq=include_dtdq, 
            include_o=include_o
        )
    )
    to_return['Name'] = team.team_name
    
    return to_return

    
def get_weekly_stats_team(
    team: Team,
    start_date: datetime.datetime, 
    end_date: datetime.datetime,
    include_dtdq=False,
    include_o=False
):
    """ Get weekly stats for an entire team"""
    to_return = reduce_roster_stats_to_team(
        get_weekly_stats_roster(
            team, start_date, end_date, include_dtdq=include_dtdq,
            include_o=include_o
        )
    )
    to_return['Name'] = team.team_name
    
    return to_return


def reduce_roster_stats_to_team(roster_stats: pd.DataFrame):
    """ Collapse a set of player stats to a single team stat"""
    summed = roster_stats[constants.keep_keys].sum().to_dict()
    summed['FG%'] = summed['FGM'] / summed['FGA']
    summed['FT%'] = summed['FTM'] / summed['FTA']
    
    return summed
    
    
def summarize_league_per_team(league: League, include_dtdq=False, include_o=False):
    """ Give stats per team in the league"""
    all_records = []
    for team in league.teams:
        record = get_avg_stats_team(
            team, 
            include_dtdq=include_dtdq, 
            include_o=include_o
        )
        record['Name'] = team.team_name
        all_records.append(record)
    return pd.DataFrame(all_records).set_index("Name").fillna(0.0)


def build_team_mapping(league: League):
    """ Relate team names to espn_api Team objects """
    return {
        team.team_name: team for team in league.teams
    }


def _is_dtdq(player: Player):
    """ Is the player's status DTD or Q? """
    return (
        (player.injuryStatus == 'DAY_TO_DAY') or
        (player.injuryStatus == 'QUESTIONABLE')
    )

def _is_out(player: Player):
    """ Is the player's status O? """
    return (player.injuryStatus == 'OUT')


def summarize_league_draft(
    league: League, 
    draft_rosters: Dict[str, List[str]], 
    include_dtdq=False,
    include_o=False
):
    """ Given a list of player names from a draft, summarize stats per team """
    all_records = []
    all_player_stats = pull_all_players(league)
    for team_name, player_name_list in draft_rosters.items():
        if len(player_name_list) > 0:
            record = reduce_roster_stats_to_team(all_player_stats.loc[player_name_list])
        else:
            record = {key: 0.0 for key in constants.keep_keys}
            record['FG%'] = 0.0
            record['FT%'] = 0.0
        record['Name'] = team_name
        all_records.append(record)
    return pd.DataFrame(all_records).set_index("Name").fillna(0.0)


@st.cache_data
def pull_all_players(
    _league, 
    week: int=None, 
    size: int=400, 
) -> pd.DataFrame:
    '''Returns a dataframe of all players and associated stats.
    By default, will include stats of DTD/Q/O players
    
    Adapted from https://github.com/cwendt94/espn-api/blob/1dda8f4c162fb80c1027987b1a5018b33db41cb6/espn_api/basketball/league.py#L115
    '''

    if _league.year < 2019:
        raise Exception('Cant use free agents before 2019')
    if not week:
        week = _league.current_week

    params = {
        'view': 'kona_player_info',
        'scoringPeriodId': week,
    }
    filters = {
        "players":{
            "limit": size,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
            "sortDraftRanks": {
                "sortPriority": 100, "sortAsc": True, "value": "STANDARD"
            }
        }
    }
    headers = {'x-fantasy-filter': json.dumps(filters)}

    data = _league.espn_request.league_get(params=params, headers=headers)
    players = data['players']
    all_players = [Player(payload, _league.year) for payload in players]
    
    all_players_stats = get_avg_stats_roster(all_players, include_dtdq=True, include_o=True)
    
    return all_players_stats
