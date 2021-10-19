from typing import Optional
from colour import Color
import pandas as pd

red = Color("#ff4d4d")
green = Color("#00b300")

def coloring(s: pd.Series, n_colors: Optional[int] = 2):
    """ Highlight cells for winning vs losing categories"""
    possible_colors = [
        f'background-color: {a.get_hex_l()}' 
        for a in green.range_to(red, n_colors)
    ]
    if s.name == 'TO':
        rankings = s.rank(ascending=True)
    else:
        rankings = s.rank(ascending=False)
    my_colors = [
        possible_colors[int(val) - 1] 
        for val in rankings.values
    ]
    
    return my_colors


def build_tooltips(df: pd.DataFrame):
    fgm = df['FGM'].round(1).astype(str)
    fga = df['FGA'].round(1).astype(str)
    ftm = df['FTM'].round(1).astype(str)
    fta = df['FTA'].round(1).astype(str)
    
    tooltips = pd.concat([
        (fgm+'/'+fga).rename("FG%"),
        (ftm+'/'+fta).rename("FT%")
    ], axis=1)
    
    return tooltips
    
    
def style_categories(df: pd.DataFrame):
    df_to_show = df.drop(columns=['FGM', 'FGA', 'FTM', 'FTA'])
    tooltips = build_tooltips(df)
    
    return (
        df_to_show.style
        .apply(coloring, n_colors=len(df_to_show))
        .format(precision=2)
        .set_tooltips(tooltips)
    )