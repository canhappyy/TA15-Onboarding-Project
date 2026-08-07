"""
Ingest landmarks -> theme / landmark_category / landmark.

Applies the US2.1 refuge allow-list (config.REFUGE_THEME_SUBTHEME_PAIRS)
at ingest time -- app-facing queries just filter WHERE is_refuge = true.
"""
import re

from sqlalchemy import create_engine, text
import pandas as pd

import config

COORD_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$")


def _parse_coords(value):
    if not isinstance(value, str):
        return None, None
    m = COORD_RE.match(value)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def load(csv_path=config.LANDMARKS_CSV, database_url: str = config.DATABASE_URL) -> dict:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    df = df.rename(columns={"Sub Theme": "Sub_Theme", "Feature Name": "Feature_Name"})
    df["Theme"] = df["Theme"].astype("string").str.strip()
    df["Sub_Theme"] = df["Sub_Theme"].astype("string").str.strip()
    df["Feature_Name"] = df["Feature_Name"].astype("string").str.strip()

    # A landmark with no Theme/Sub Theme can't be filed into the
    # Theme->Category chain, and one with no name is useless to show a
    # user -- drop and say how many, rather than let a NaN "theme"
    # become its own bogus category.
    before = len(df)
    df = df.dropna(subset=["Theme", "Sub_Theme", "Feature_Name"])
    if len(df) < before:
        print(f"  dropped {before - len(df)} landmark(s) missing Theme, Sub Theme, or Feature Name")

    lat_lon = df["Co-ordinates"].apply(_parse_coords)
    df["Latitude"] = lat_lon.apply(lambda t: t[0])
    df["Longitude"] = lat_lon.apply(lambda t: t[1])
    bad_coords = df["Latitude"].isna() | df["Longitude"].isna()
    if bad_coords.any():
        print(f"  {bad_coords.sum()} landmark(s) had unparseable coordinates "
              f"(kept, but won't show up in radius-based refuge lookups)")

    # Not dropped -- same feature name can  appear more than
    # once (e.g. a park with several distinct entry points)
    dupe_names = df.duplicated(subset=["Feature_Name", "Theme", "Sub_Theme"]).sum()
    if dupe_names:
        print(f"  note: {dupe_names} landmark(s) share a Feature Name + Theme + Sub Theme "
              f"with another row (kept -- verify these are distinct locations, not duplicate entries)")

    refuge_pairs = set(config.REFUGE_THEME_SUBTHEME_PAIRS)

    themes = df[["Theme", "Sub_Theme"]].drop_duplicates().reset_index(drop=True)
    themes["theme_id"] = themes.index + 1
    themes["category_id"] = themes.index + 1
    themes["category_name"] = themes["Sub_Theme"].map(config.CATEGORY_DISPLAY_NAMES).fillna(
        themes["Sub_Theme"]
    )
    themes["is_refuge"] = themes.apply(
        lambda r: (r["Theme"], r["Sub_Theme"]) in refuge_pairs, axis=1
    )
    themes = themes.rename(columns={"Theme": "theme", "Sub_Theme": "sub_theme"})

    df = df.merge(
        themes[["theme", "sub_theme", "category_id"]],
        left_on=["Theme", "Sub_Theme"], right_on=["theme", "sub_theme"],
    )
    df = df.rename(columns={"Feature_Name": "feature_name", "Latitude": "latitude", "Longitude": "longitude"})

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM landmark"))
        conn.execute(text("DELETE FROM landmark_category"))
        conn.execute(text("DELETE FROM theme"))
        conn.execute(text("ALTER SEQUENCE theme_theme_id_seq RESTART WITH 1"))
        conn.execute(text("ALTER SEQUENCE landmark_category_category_id_seq RESTART WITH 1"))

        themes[["theme_id", "theme", "sub_theme"]].to_sql(
            "theme", conn, if_exists="append", index=False
        )
        themes[["category_id", "theme_id", "category_name", "is_refuge"]].to_sql(
            "landmark_category", conn, if_exists="append", index=False
        )
        df[["category_id", "feature_name", "latitude", "longitude"]].to_sql(
            "landmark", conn, if_exists="append", index=False
        )

    stats = {
        "themes": len(themes),
        "landmarks": len(df),
        "refuge_categories": int(themes["is_refuge"].sum()),
        "refuge_landmarks": int(df["category_id"].isin(
            themes.loc[themes["is_refuge"], "category_id"]
        ).sum()),
    }
    print(
        f"landmark: loaded {stats['landmarks']} landmarks across {stats['themes']} "
        f"theme/sub-theme combos ({stats['refuge_landmarks']} flagged as refuges "
        f"under {stats['refuge_categories']} refuge categories)"
    )
    return stats


if __name__ == "__main__":
    load()