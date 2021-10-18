import datetime
from typing import Optional
import pandas as pd
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


def get_avg_stats_player(player: Player):
    """ Pull stats for partiucular player
    Stats prefaced with '00' are actual, observed stats
    Stats prefaced with '10' are predicted stats for that season
    
    """
    if '002021' in player.stats:
        stats_to_add = player.stats['002021']['avg']
    elif '102022' in player.stats:
        stats_to_add = player.stats['102022']['avg']
    else:
        warnings.warn(f"Can't find stats for player {player}")
    return stats_to_add


def get_weekly_stats_player(
    player: Player, 
    start_date: datetime.datetime, 
    end_date: datetime.datetime, 
    team_id_name_mapping: Optional[dict] = None, 
    schedule: Optional[pd.DataFrame] = None
):
    """ Given a time range, predict categories"""
    if team_id_name_mapping is None:
        team_id_name_mapping = constants.load_team_name_mapping()
    if schedule is None:
        schedule = constants.load_pro_schedule()
        
    team_id = team_id_name_mapping[player.proTeam.upper()]
    num_games = get_num_games(schedule, team_id, start_date, end_date)
    player_avg_stats = get_avg_stats_player(player)
    
    relevant_stats = {
        k: num_games * player_avg_stats[k] 
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


def get_avg_stats_roster(team: Team):
    """ For a fantasy team, get per-game-averaged for each player """
    all_records = []
    for player in team.roster:
        player_stats = get_avg_stats_player(player)
        player_stats['Name'] = player.name
        all_records.append(player_stats)
        
    return (
        pd.DataFrame(all_records)
        .set_index("Name")
    )


def get_weekly_stats_roster(
    team: Team, 
    start_date: datetime.datetime, 
    end_date: datetime.datetime
):
    """ For a fantasy team, project categories for roster """
    all_records = []
    for player in team.roster:
        entry = get_weekly_stats_player(
            player, start_date, end_date
        )
        entry['Name'] = player.name
        all_records.append(entry)
        
    return pd.DataFrame(all_records).set_index("Name")


def get_avg_stats_team(team: Team):
    to_return = reduce_roster_stats_to_team(
        get_avg_stats_roster(team)
    )
    to_return['Name'] = team.team_name
    
    return to_return

    
def get_weekly_stats_team(
    team: Team,
    start_date: datetime.datetime, 
    end_date: datetime.datetime
):
    to_return = reduce_roster_stats_to_team(
        get_weekly_stats_roster(team, start_date, end_date)
    )
    to_return['Name'] = team.team_name
    
    return to_return


def reduce_roster_stats_to_team(roster_stats: pd.DataFrame):
    summed = roster_stats[constants.keep_keys].sum().to_dict()
    summed['FG%'] = summed['FGM'] / summed['FGA']
    summed['FT%'] = summed['FTM'] / summed['FTA']
    
    return summed
    