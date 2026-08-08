"""
Ingest landmarks -> theme / landmark_category / landmark.

Applies the US2.1 refuge allow-list (config.REFUGE_THEME_SUBTHEME_PAIRS)
at ingest time -- app-facing queries just filter WHERE is_refuge = true.
"""
import re

from sqlalchemy import create_engine, text
import pandas as pd

import config
from transforms import transform_landmarks

COORD_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$")


def _parse_coords(value):
    if not isinstance(value, str):
        return None, None
    m = COORD_RE.match(value)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def load(csv_path=config.LANDMARKS_CSV, database_url: str = config.DATABASE_URL) -> dict:
    transformed = transform_landmarks(pd.read_csv(csv_path, encoding="utf-8-sig"))
    df = pd.DataFrame.from_records(transformed["records"])
    if transformed["rejected_count"]:
        print(f"  dropped {transformed['rejected_count']} invalid landmark(s)")

    # Not dropped -- same feature name can  appear more than
    # once (e.g. a park with several distinct entry points)
    dupe_names = df.duplicated(subset=["feature_name", "theme", "sub_theme"]).sum()
    if dupe_names:
        print(f"  note: {dupe_names} landmark(s) share a Feature Name + Theme + Sub Theme "
              f"with another row (kept -- verify these are distinct locations, not duplicate entries)")

    refuge_pairs = set(config.REFUGE_THEME_SUBTHEME_PAIRS)

    themes = df[["theme", "sub_theme"]].drop_duplicates().reset_index(drop=True)
    themes["theme_id"] = themes.index + 1
    themes["category_id"] = themes.index + 1
    themes["category_name"] = themes["sub_theme"].map(config.CATEGORY_DISPLAY_NAMES).fillna(
        themes["sub_theme"]
    )
    themes["is_refuge"] = themes.apply(
        lambda r: (r["theme"], r["sub_theme"]) in refuge_pairs, axis=1
    )

    df = df.merge(
        themes[["theme", "sub_theme", "category_id"]],
        on=["theme", "sub_theme"],
    )

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
