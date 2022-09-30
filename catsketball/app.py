import datetime
from espn_api.basketball import League
import pandas as pd
import streamlit as st
st.set_page_config(
    page_title='Catsketball', page_icon=':basketball:', layout="wide"
)

import constants, espn_stats, styling

st.title("Fantasy basketball team analyzer (ESPN)")
# This first form submits ESPN league settings
# Saving them to streamlit session state
with st.expander("ESPN league cookies"):
    league_info_form = st.form(key='league_info_form')
    with league_info_form:
        st.markdown(
            "[How to access ESPN fantasy league cookies]" + 
            "(https://github.com/cwendt94/espn-api/discussions/150)"
        )
        league_id = st.text_input("League ID: ", key='league_id')
        espn_s2 = st.text_input(
            "ESPN S2: ", type='password', key='espn_s2'
        )
        swid = st.text_input("SWID: ", type='password', key='swid')
        league_info_form_submit = st.form_submit_button(
            "Submit ESPN league cookies"
        )

    
# If espn-league cookies are in session state, proceed
if (
    (st.session_state.get("league_id", '') != '') and 
    (st.session_state.get("espn_s2", '') != '') and 
    (st.session_state.get("swid", '') != '')
):
    league = League(
        league_id=st.session_state['league_id'],
        espn_s2=st.session_state['espn_s2'],
        swid=st.session_state['swid'],
        year=2022
    )
    team_mapping = espn_stats.build_team_mapping(league)

    include_dtdq = st.checkbox(
        "Include day-to-day/questionable players " +
        "(IR players are always ignored)"
    )
    include_o = st.checkbox("Include out players")

    with st.expander("League summary"):
        st.text("Sum of each player's per-game average")
        league_summary = espn_stats.summarize_league_per_team(
            league, include_dtdq=include_dtdq, include_o=include_o
        )
        st.markdown(
            styling.style_categories(league_summary).to_html(),
            unsafe_allow_html=True
        )
        st.caption("Ignoring players on IR")
        

    with st.expander("Weekly comparisons"):
        all_teams = st.multiselect(
            "Choose teams: ",
            options=[a.team_name for a in league.teams]
        )
        date_selector = st.date_input(
            "Select date range, including start date, up to (and not including) end date: ",
            value=(datetime.date.today(), datetime.date.today())
        )
        
        if len(date_selector) == 2:
            start_date, end_date = date_selector
        else:
            st.error("Choose two valid dates")
            st.stop()
        start_date = datetime.datetime.combine(
            start_date, datetime.datetime.min.time()
        )
        end_date = datetime.datetime.combine(
            end_date, datetime.datetime.min.time()
        )
        if (len(all_teams) > 0) and (start_date != end_date):
            all_team_stats = []
            for team in all_teams:
                team_i = espn_stats.get_weekly_stats_team(
                    team_mapping[team], start_date, end_date,
                    include_dtdq=include_dtdq,
                    include_o=include_o
                )
                team_i['Name'] = team
                all_team_stats.append(team_i)
            h2h_comparison = (
                pd.DataFrame(all_team_stats)
                .set_index("Name")
            )
            st.markdown(
                styling.style_categories(h2h_comparison).to_html(),
                unsafe_allow_html=True
            )
        st.caption("Ignoring players on IR")


    with st.expander("Team builder"):
        all_players = espn_stats.pull_all_players(league)
        player_names = list(all_players.index)

        n_cols = 3
        all_columns = st.columns(n_cols)

        team_rosters = {} # Map team name to list of player names
        for i, team in enumerate(league.teams):
            col_selector = (i % 3)
            team_rosters[team.team_name] = (
                all_columns[col_selector].multiselect(
                    f"{team.team_name}", options=player_names
                )
            )
        draft_summary = espn_stats.summarize_league_draft(
            league, team_rosters, include_dtdq=include_dtdq,
            include_o=include_o
        )

        st.markdown(
            styling.style_categories(draft_summary).to_html(),
            unsafe_allow_html=True
        )
