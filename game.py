import math


EARTH_RADIUS = 6371.0


def calculate_distance(city1, city2):
    """
    2都市間の直線距離をkmで返す。
    Haversine formula。
    """

    lat1 = math.radians(
        float(city1["latitude"])
    )

    lon1 = math.radians(
        float(city1["longitude"])
    )

    lat2 = math.radians(
        float(city2["latitude"])
    )

    lon2 = math.radians(
        float(city2["longitude"])
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.asin(
        math.sqrt(a)
    )

    return EARTH_RADIUS * c


def is_within_distance(
    current_city,
    next_city,
    max_distance
):
    """
    MAX_DISTANCE以内か判定。
    """

    distance = calculate_distance(
        current_city,
        next_city
    )

    return distance <= max_distance


def get_remaining_time(
    start_time,
    time_limit
):
    """
    残り時間を秒で返す。
    """

    import time

    elapsed = time.time() - start_time

    remaining = max(
        0,
        time_limit - elapsed
    )

    return remaining


def format_time(seconds):
    """
    秒をMM:SS形式にする。
    """

    seconds = int(max(0, seconds))

    minutes = seconds // 60
    secs = seconds % 60

    return f"{minutes:02d}:{secs:02d}"


def is_time_up(
    start_time,
    time_limit
):
    return get_remaining_time(
        start_time,
        time_limit
    ) <= 0


def is_goal(
    current_city,
    goal_city
):
    """
    GeoNames IDでGOAL到達判定。
    """

    return (
        current_city["geonameid"]
        == goal_city["geonameid"]
    )


def make_move(
    current_city,
    next_city,
    total_distance,
    visited_cities
):
    """
    1回の移動を反映する。
    """

    distance = calculate_distance(
        current_city,
        next_city
    )

    total_distance += distance

    visited_cities.append(
        next_city
    )

    return (
        next_city,
        total_distance,
        visited_cities,
        distance,
    )