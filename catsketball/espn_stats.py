from collections import defaultdict
import datetime
from typing import Optional
import pandas as pd
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


def get_avg_stats_player(player: Player):
    """ Pull stats for partiucular player
    Stats prefaced with '00' are actual, observed stats
    Stats prefaced with '10' are predicted stats for that season
    
    Lots of different ways to estimate stats for players,
    naively average the different estimates to get the
    average stats for a particular player
    """
    # Ignore player if on IR
    # If a player is injured but NOT on IR, still factor his stats
    stat_estimates = []
    if player.lineupSlot == "IR":
        return defaultdict(int)
    if '002021' in player.stats:
        stat_estimates.append(player.stats['002021']['avg'])
    if '102022' in player.stats:
        stat_estimates.append(player.stats['102022']['avg'])
    if '002022' in player.stats:
        stat_estimates.append(player.stats['002022']['avg'])
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
    stats_to_add['FG%'] = stats_to_add['FGM'] / stats_to_add['FGA']
    stats_to_add['FT%'] = stats_to_add['FTM'] / stats_to_add['FTA']
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
    # Ignore player if injured or IR
    if player.injured or (player.lineupSlot=="IR"):
        relevant_stats = {
            k: 0
            for k in constants.keep_keys
        }
        relevant_stats['FG%'] = 0
        relevant_stats['FT%'] = 0
    
    else:
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
    """ For a fantasy team, get per-game-averaged stats 
    for each player """
    all_records = []
    for player in team.roster:
        player_stats = get_avg_stats_player(player)
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
        
    return pd.DataFrame(all_records).set_index("Name").fillna(0.0)


def get_avg_stats_team(team: Team):
    """ Get average stats for an entire team"""
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
    """ Get weekly stats for an entire team"""
    to_return = reduce_roster_stats_to_team(
        get_weekly_stats_roster(team, start_date, end_date)
    )
    to_return['Name'] = team.team_name
    
    return to_return


def reduce_roster_stats_to_team(roster_stats: pd.DataFrame):
    """ Collapse a set of player stats to a single team stat"""
    summed = roster_stats[constants.keep_keys].sum().to_dict()
    summed['FG%'] = summed['FGM'] / summed['FGA']
    summed['FT%'] = summed['FTM'] / summed['FTA']
    
    return summed
    
    
def summarize_league_per_team(league):
    """ Give stats per team in the league"""
    all_records = []
    for team in league.teams:
        record = get_avg_stats_team(team)
        record['Name'] = team.team_name
        all_records.append(record)
    return pd.DataFrame(all_records).set_index("Name").fillna(0.0)


def build_team_mapping(league):
    return {
        team.team_name: team for team in league.teams
    }
