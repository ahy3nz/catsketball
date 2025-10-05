import copy
import re
import requests
from typing import Any, Dict, Optional

import numpy as np
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.csv as csv
import pyarrow.compute as pc
from scipy.stats import zscore
from sklearn.preprocessing import StandardScaler
import streamlit as st

STAT_COLS = ["FG%", "FT%", "3PM", "PTS", "TREB", "AST", "STL", "BLK", "TO"]
POSITIONS = ["PG", "SG", "SF", "PF", "C"]
RE_PATTERN = r'^(\d+)*'#\s*(.*)'

@st.cache_data
def load_projections() -> pa.Table:
    # html_content = requests.get("https://hashtagbasketball.com/fantasy-basketball-projections").content
    # pd_tables = pd.read_html(html_content)
    # pd_df = pd_tables[2][lambda df_: df_["R#"] != "R#"]
    # pd_df["R#"] = pd_df["R#"].apply(lambda val: re.search(RE_PATTERN, val).group(0))
    # pd_df = (
    #     pd_df
    #     .astype({
    #         "R#": "int",
    #         "ADP": "float",
    #         "GP": "int",
    #         "3PM": "float",
    #         "PTS": "float",
    #         "TREB": "float",
    #         "AST": "float",
    #         "STL": "float",
    #         "BLK": "float",
    #         "TO": "float"
    #     })
    # )
    # df = pa.Table.from_pandas(pd_df)
    # fg_index = df.schema.names.index("FG%")
    # ft_index = df.schema.names.index("FT%")
    # df = (
    #     df.append_column("drafted_by", [[0]*len(df)])
    #     .set_column(
    #         fg_index, "FG%", 
    #         [[format_percentages(a) for a in df["FG%"]]]
    #     )
    #     .set_column(
    #         ft_index, "FT%", 
    #         [[format_percentages(a) for a in df["FT%"]]]
    #     )
    # )
    # for pos in POSITIONS:
    #     df = df.append_column(pos, pc.count_substring(df["POS"], pos))
    
    # df = (
    #     df.sort_by("ADP")
    #     .select(["PLAYER", "R#", "ADP", "GP", "drafted_by", "POS", "TEAM", *STAT_COLS, "MPG", *POSITIONS])
    # )
    df = (
        #pd.read_csv("./staticdata/nba_projections_full_1_77.csv")
        pd.read_html("https://fanscout.pro/projections")[0]
        .rename(columns={
            "Name": "PLAYER",
            "G": "GP",
            "M": "MPG",
            "TPM": "3PM",
            "REB": "TREB",
            "TOV": "TO"
        })
        .pipe(remove_percentage_symbol)
        .pipe(compute_fgm_fta)
        .sort_values("Value", ascending=False)
        .assign(
            POS=None,
            drafted_by=0,
        )
    )
    df = pa.Table.from_pandas(df)
    
    return df


def format_percentages(pa_string):
    """ In some projections, percentages are labelled as X (Y/Z), 
    remove the (Y/Z) substring"""
    val = pa_string.as_py()
    if "(" in val:
        return float(val[0:val.index('(')])
    else:
        return float(val)

def remove_percentage_symbol(pd_df):
    pd_df["FG%"] = pd_df["FG%"].str.rstrip("%").astype(float)
    pd_df["FT%"] = pd_df["FT%"].str.rstrip("%").astype(float)
    return pd_df

def compute_fgm_fta(pd_df):
    return pd_df.assign(
        FGM=lambda df_: df_["FG%"] * df_["FGA"],
        FTM=lambda df_: df_["FT%"] * df_["FTA"],
    )
    
    
def encode_positions(val):
    """ Encode positions in separate columns"""
    positions = {
        pos: False
        for pos in POSITIONS
    }
    for code in val.split(","):
        positions[code] = True
    return pd.Series(positions)


def init_standardizers() -> Dict[str, StandardScaler]:
    return {stat: StandardScaler() for stat in STAT_COLS}
 
    
def fit_standardizers(
    table: pa.Table,
    standardizers: Dict[str, StandardScaler]
) -> None:
    """ Fit standardizers to players who not been drafted"""
    for stat, standardizer in standardizers.items():
        standardizer.fit(
            table
            .filter(pc.equal(table["drafted_by"], 0))
            [stat]
            .to_numpy()
            .reshape(-1,1)
        )
        
def standardize(
    table: pa.Table,
    standardizers: Dict[str, StandardScaler]
) -> pa.Table:
    """ Apply standardizers to all players"""
    stdzd_table = copy.copy(table)
    for stat, standardizer in standardizers.items():
        col_idx = stdzd_table.schema.names.index(stat)
        stdzd_table = stdzd_table.set_column(
            col_idx, stat,
            standardizer.transform(stdzd_table[stat].to_numpy().reshape(-1,1))
        )
        
    return stdzd_table

def update_zscores() -> None:
    change_info = st.session_state.drafting_changes["edited_rows"]
    drafted_col = st.session_state.projections_modified["drafted_by"].to_pylist()
    for idx, change_dict in change_info.items():
         drafted_col[idx] = change_dict["drafted_by"]
            
    drafted_index = st.session_state.projections_modified.schema.names.index("drafted_by")
    st.session_state.projections_modified = (
        st.session_state.projections_modified
        .set_column(
            drafted_index, "drafted_by", 
            [drafted_col]
        )
    )
            
    fit_standardizers(
        st.session_state.projections_modified, 
        st.session_state.standardizers
    )
    
    stdzd_table = standardize(
        st.session_state.projections_modified, 
        st.session_state.standardizers
    )
    
    st.session_state.stdzd_table = stdzd_table.to_pandas()

def compare_teams(df: Optional[pd.DataFrame]) -> Any:
    if df is None: 
        return None
    grouped = df.groupby("drafted_by")[["GP", *STAT_COLS]].sum()
    return grouped
