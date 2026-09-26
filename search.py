import re
import unicodedata
from difflib import get_close_matches, SequenceMatcher

import pandas as pd


FUZZY_CUTOFF = 0.75
MIN_SEARCH_LENGTH = 3


# =========================================================
# Manual aliases
# =========================================================

MANUAL_ALIASES = {
    "NYC": "New York",
    "New York City": "New York",
    "LA": "Los Angeles",
    "SF": "San Francisco",
    "DC": "Washington",

    "東京": "Tokyo",
    "大阪": "Osaka",
    "京都": "Kyoto",
    "横浜": "Yokohama",
    "名古屋": "Nagoya",
    "神戸": "Kobe",
    "札幌": "Sapporo",
    "福岡": "Fukuoka",
    "広島": "Hiroshima",
    "仙台": "Sendai",
    "静岡": "Shizuoka",
    "大垣": "Ogaki",
    "大津": "Otsu",
}


# =========================================================
# Normalize
# =========================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    text = unicodedata.normalize(
        "NFKC",
        text
    )

    text = text.casefold()

    text = text.replace("-", " ")
    text = text.replace("_", " ")

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


# =========================================================
# Search index
# =========================================================

def build_search_index(cities):

    search_index = {}

    def add(name, row_index):

        if pd.isna(name):
            return

        key = normalize_text(name)

        if not key:
            return

        if key not in search_index:
            search_index[key] = []

        if row_index not in search_index[key]:
            search_index[key].append(row_index)

    # -----------------------------------------
    # GeoNames names
    # -----------------------------------------

    for idx, row in cities.iterrows():

        add(
            row["name"],
            idx
        )

        add(
            row["ascii_name"],
            idx
        )

        if not pd.isna(
            row["alternate_names"]
        ):

            for alias in str(
                row["alternate_names"]
            ).split(","):

                add(
                    alias,
                    idx
                )

    # -----------------------------------------
    # Manual aliases
    # -----------------------------------------

    for alias, official_name in (
        MANUAL_ALIASES.items()
    ):

        official_key = normalize_text(
            official_name
        )

        for idx in search_index.get(
            official_key,
            []
        ):

            add(
                alias,
                idx
            )

    return search_index


# =========================================================
# Exact search
# =========================================================

def exact_search_city(
    cities,
    search_index,
    query
):

    key = normalize_text(query)

    if not key:
        return []

    return list(
        search_index.get(
            key,
            []
        )
    )


# =========================================================
# Fuzzy search
# =========================================================

def fuzzy_search_city(
    cities,
    search_index,
    query,
    n=10,
    cutoff=FUZZY_CUTOFF
):

    key = normalize_text(query)

    if len(key) < MIN_SEARCH_LENGTH:
        return []

    search_keys = list(
        search_index.keys()
    )

    matches = get_close_matches(
        key,
        search_keys,
        n=n,
        cutoff=cutoff,
    )

    results = []

    for match in matches:

        score = SequenceMatcher(
            None,
            key,
            match
        ).ratio()

        for idx in search_index[
            match
        ]:

            results.append(
                {
                    "index": idx,
                    "score": score,
                    "matched_key": match,
                }
            )

    # 同じ都市の重複を削除
    unique = {}

    for result in results:

        idx = result["index"]

        if (
            idx not in unique
            or result["score"]
            > unique[idx]["score"]
        ):

            unique[idx] = result

    results = list(
        unique.values()
    )

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results


# =========================================================
# City display
# =========================================================

def city_display_name(city):

    name = str(
        city["name"]
    )

    country_code = str(
        city["country_code"]
    )

    country = city.get(
        "country",
        ""
    )

    admin1 = city.get(
        "admin1_name",
        ""
    )

    if pd.isna(country):
        country = ""

    if pd.isna(admin1):
        admin1 = ""

    # 例：
    # Amsterdam — Netherlands
    # Amsterdam — New York, United States
    # Tokyo — Tokyo, Japan

    location_parts = []

    if admin1:
        location_parts.append(
            str(admin1)
        )

    if country:
        location_parts.append(
            str(country)
        )

    if location_parts:

        location = ", ".join(
            location_parts
        )

        return (
            f"{name} — "
            f"{location} "
            f"({country_code})"
        )

    return (
        f"{name} "
        f"({country_code})"
    )


# =========================================================
# BallTree Filter (NEW)
# =========================================================
import numpy as np
EARTH_RADIUS = 6371.0

def get_valid_indices(tree, current_city, max_distance):
    """BallTreeを使用して距離内の都市のインデックスを瞬時に取得"""
    current_lat = np.radians(float(current_city["latitude"]))
    current_lon = np.radians(float(current_city["longitude"]))
    radius_rad = max_distance / EARTH_RADIUS
    indices = tree.query_radius([[current_lat, current_lon]], r=radius_rad)[0]
    return set(indices)

# =========================================================
# Exact search
# =========================================================
def exact_search_city(cities, search_index, query, valid_indices=None):
    key = normalize_text(query)
    if not key: return []
    results = search_index.get(key, [])
    if valid_indices is not None:
        results = [idx for idx in results if idx in valid_indices]
    return list(results)

# =========================================================
# Fuzzy search
# =========================================================
def fuzzy_search_city(cities, search_index, query, n=10, cutoff=FUZZY_CUTOFF, valid_indices=None):
    key = normalize_text(query)
    if len(key) < MIN_SEARCH_LENGTH: return []

    if valid_indices is not None:
        # BallTreeで絞った「距離内の都市名」のみにFuzzy検索をかけることで劇的に高速化
        search_keys = [k for k, indices in search_index.items() if any(idx in valid_indices for idx in indices)]
    else:
        search_keys = list(search_index.keys())

    matches = get_close_matches(key, search_keys, n=n, cutoff=cutoff)
    results = []
    for match in matches:
        score = SequenceMatcher(None, key, match).ratio()
        for idx in search_index[match]:
            if valid_indices is not None and idx not in valid_indices: continue
            results.append({"index": idx, "score": score, "matched_key": match})

    unique = {}
    for result in results:
        idx = result["index"]
        if idx not in unique or result["score"] > unique[idx]["score"]:
            unique[idx] = result
    results = list(unique.values())
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# =========================================================
# Exact & Fuzzy candidates
# =========================================================
def get_exact_candidates(cities, search_index, query, valid_indices=None):
    indices = exact_search_city(cities, search_index, query, valid_indices)
    return [cities.loc[idx] for idx in indices]

def get_fuzzy_candidates(cities, search_index, query, valid_indices=None):
    # valid_indices をキーワード引数として明示的に渡すように修正
    results = fuzzy_search_city(cities, search_index, query, valid_indices=valid_indices)
    candidates = []
    for result in results:
        city = cities.loc[result["index"]]
        candidates.append({"city": city, "score": result["score"], "matched_key": result["matched_key"]})
    return candidates
    for result in results:
        city = cities.loc[result["index"]]
        candidates.append({"city": city, "score": result["score"], "matched_key": result["matched_key"]})
    return candidates

# =========================================================
# Search all candidates
# =========================================================
def search_city_candidates(cities, search_index, query, current_city=None, max_distance=None, calculate_distance_func=None, fuzzy=False, tree=None):
    valid_indices = None
    # BallTreeを使って検索範囲を絞り込む
    if current_city is not None and max_distance is not None and tree is not None:
        valid_indices = get_valid_indices(tree, current_city, max_distance)

    exact_candidates = get_exact_candidates(cities, search_index, query, valid_indices)
    if exact_candidates:
        results = []
        for city in exact_candidates:
            distance = calculate_distance_func(current_city, city) if current_city is not None and calculate_distance_func else None
            results.append({"city": city, "distance": distance, "score": 1.0, "fuzzy": False})
        return results

    if not fuzzy: return []

    fuzzy_candidates = get_fuzzy_candidates(cities, search_index, query, valid_indices)
    results = []
    for item in fuzzy_candidates:
        city = item["city"]
        distance = calculate_distance_func(current_city, city) if current_city is not None and calculate_distance_func else None
        results.append({"city": city, "distance": distance, "score": item["score"], "fuzzy": True})
    return results