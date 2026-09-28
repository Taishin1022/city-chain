import re
import unicodedata
from difflib import get_close_matches, SequenceMatcher

import pandas as pd
import numpy as np

FUZZY_CUTOFF = 0.75
MIN_SEARCH_LENGTH = 3
EARTH_RADIUS = 6371.0


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
# City Priority Helper (NEW)
# =========================================================

def get_city_priority(city_row):
    """
    都市の優先度を算出する関数。
    1. population（人口）があればそれを数値化して使用
    2. feature_code（都市の規模/種類）があればボーナススコアを付与
    """
    score = 0.0
    
    # 1. 人口(population)の処理 (カンマ等の文字列エラー対策)
    if "population" in city_row:
        pop_val = city_row["population"]
        if pd.notna(pop_val) and pop_val != "":
            try:
                if isinstance(pop_val, str):
                    pop_val = pop_val.replace(",", "")
                score += float(pop_val)
            except:
                pass
                
    # 2. feature_code（都市区分）の処理（GeoNamesデータの強力なフォールバック）
    # PPLC(首都) > PPLA(州都/一級行政区) > PPLA2 > PPL(一般都市)
    if "feature_code" in city_row:
        fc = str(city_row["feature_code"]).upper()
        if fc == "PPLC":
            score += 100000000  # 首都（イギリスのロンドン等）には1億人相当の優先度
        elif fc == "PPLA":
            score += 10000000
        elif fc == "PPLA2":
            score += 1000000
        elif fc == "PPL":
            score += 10000
            
    return score


# =========================================================
# BallTree Filter 
# =========================================================

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
            
    results_list = list(unique.values())

    # 類似度スコア(score) を最優先し、同スコアなら優先度（首都＋人口）の順でソート
    results_list.sort(
        key=lambda x: (x["score"], get_city_priority(cities.loc[x["index"]])), 
        reverse=True
    )
    return results_list


# =========================================================
# Exact & Fuzzy candidates
# =========================================================

def get_exact_candidates(cities, search_index, query, valid_indices=None):
    indices = exact_search_city(cities, search_index, query, valid_indices)
    
    # インデックスから都市データを取得
    candidates = [cities.loc[idx] for idx in indices]
    
    # ここで「完全一致」の都市群を、優先度（人口＋首都ボーナス）順にソートする
    candidates.sort(key=get_city_priority, reverse=True)
    
    return candidates

def get_fuzzy_candidates(cities, search_index, query, valid_indices=None):
    results = fuzzy_search_city(cities, search_index, query, valid_indices=valid_indices)
    candidates = []
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