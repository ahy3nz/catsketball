import copy
import datetime
from espn_api.basketball import League
import pandas as pd
from scipy.stats import zscore
import streamlit as st
st.set_page_config(
    page_title='Catsketball', page_icon=':basketball:', layout="wide"
)

import constants, espn_stats, stat_analysis, styling

st.title(":basketball:")
league_tab, player_tab = st.tabs(["League-based comparisons", "Static player comparisons"])
# This first form submits ESPN league settings
# Saving them to streamlit session state
with league_tab:
    st.title("Fantasy basketball team analyzer (ESPN)")
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
            year=2024
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

with player_tab:
    if "projections" not in st.session_state:
        st.session_state.projections = stat_analysis.load_projections()
    if "projections_modified" not in st.session_state:
        st.session_state.projections_modified = copy.copy(stat_analysis.load_projections())
    if "standardizers" not in st.session_state:
        st.session_state.standardizers = stat_analysis.init_standardizers()
    if "stdzd_table" not in st.session_state:
        stat_analysis.fit_standardizers(
            st.session_state.projections_modified, 
            st.session_state.standardizers
        )
        
        stdzd_table = stat_analysis.standardize(
            st.session_state.projections_modified, 
            st.session_state.standardizers
        )
        
        st.session_state.stdzd_table = stdzd_table.to_pandas()
        
    st.header("Stat projections")
    st.caption("Modify the `drafted_by` column to update subsequent tables")
    st.data_editor(
        st.session_state.projections_modified.select([
            "PLAYER", "R#", "ADP", "drafted_by", "POS", 
            "TEAM", "GP", *stat_analysis.STAT_COLS, "MPG",
        ]),
        hide_index=True,
        disabled=["PLAYER", "R#", "ADP", "POS", "TEAM", "GP", *stat_analysis.STAT_COLS, "MPG"],
        use_container_width=True,
        on_change=stat_analysis.update_zscores,
        key="drafting_changes"
    )
    st.header("Relative stats")
    st.caption("Z-scores compared to players who are still available")
    if st.session_state.stdzd_table is not None:
        st.dataframe(
            st.session_state.stdzd_table[lambda df_: df_["drafted_by"] == 0]
            [["PLAYER", "R#", "ADP", "drafted_by", "POS", 
                "TEAM", "GP", *stat_analysis.STAT_COLS, "MPG",
            ]]
        )
        st.header("Team comparison")
        team_comparison = stat_analysis.compare_teams(st.session_state.stdzd_table)
        st.dataframe(styling.style_categories(
            team_comparison.drop(index=[0]), include_tooltips=False,
            use_container_width=True,
        ))

    else:
        st.dataframe(None)
        st.header("Team comparison")
        st.dataframe(None)

    st.header("Positional comparison")
    st.caption("Z-scores of players within position")
    for pos in stat_analysis.POSITIONS:
        with st.expander(pos):
            projections = (
                st.session_state.projections_modified.to_pandas()
                [lambda df_: df_[pos]==1]
            )
            projections[stat_analysis.STAT_COLS] = projections[stat_analysis.STAT_COLS].apply(zscore)
            st.dataframe(projections.drop(columns=stat_analysis.POSITIONS), use_container_width=True)

