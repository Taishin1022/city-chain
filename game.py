import math

EARTH_RADIUS = 6371.0

def calculate_distance(city1, city2):
    """
    2都市間の直線距離をkmで返す。
    Haversine formula。
    """
    lat1 = math.radians(float(city1["latitude"]))
    lon1 = math.radians(float(city1["longitude"]))
    lat2 = math.radians(float(city2["latitude"]))
    lon2 = math.radians(float(city2["longitude"]))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS * c


def is_within_distance(current_city, next_city, max_distance):
    """
    MAX_DISTANCE以内か判定。
    """
    distance = calculate_distance(current_city, next_city)
    return distance <= max_distance


def is_goal(current_city, goal_city):
    """
    GeoNames IDでGOAL到達判定。
    """
    return current_city["geonameid"] == goal_city["geonameid"]


def make_move(current_city, next_city, total_distance, visited_cities):
    """
    1回の移動を反映する。
    """
    distance = calculate_distance(current_city, next_city)
    total_distance += distance
    visited_cities.append(next_city)

    return (
        next_city,
        total_distance,
        visited_cities,
        distance,
    )


def calculate_route_efficiency(start_city, goal_city, current_city, total_distance):
    """
    リアルタイムのルート効率（%）を計算する。
    (スタート〜ゴールの直線距離) / (実際の移動距離 + 現在地からゴールまでの直線距離) * 100
    """
    ideal_distance = calculate_distance(start_city, goal_city)
    
    # スタート直後は100%
    if total_distance == 0:
        return 100.0
    
    # 推定総移動距離 ＝ 実際の移動距離 ＋ 現在地からゴールまでの直線距離
    current_to_goal = calculate_distance(current_city, goal_city)
    estimated_total = total_distance + current_to_goal
    
    if estimated_total == 0:
        return 100.0
        
    efficiency = (ideal_distance / estimated_total) * 100
    
    # 誤差吸収のため最大100%・最小0%に丸める
    return min(100.0, max(0.0, efficiency))