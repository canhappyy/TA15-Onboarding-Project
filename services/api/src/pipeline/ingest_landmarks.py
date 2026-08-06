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
    df["Theme"] = df["Theme"].str.strip()
    df["Sub_Theme"] = df["Sub_Theme"].str.strip()
    df["Feature_Name"] = df["Feature_Name"].str.strip()

    lat_lon = df["Co-ordinates"].apply(_parse_coords)
    df["Latitude"] = lat_lon.apply(lambda t: t[0])
    df["Longitude"] = lat_lon.apply(lambda t: t[1])

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
        # Reset identity sequences so Category_id/Theme_id line up with what we assigned above
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
