import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS = 6371.0

def load_cities():
    """
    ローカルの事前処理済みCSVを読み込む。
    (外部通信によるダウンロードと結合を排除し、クラッシュを防ぐ)
    """
    cities = pd.read_csv(
        "cities_processed.csv.gz", 
        dtype={"geonameid": "Int64"},
        keep_default_na=False
    )
    return cities

def build_tree(cities):
    """
    都市座標からBallTreeを作成。
    距離計算はhaversine。
    """
    lat_lon = cities[["latitude", "longitude"]].astype(np.float64).to_numpy()
    coordinates = np.radians(lat_lon)
    tree = BallTree(coordinates, metric="haversine")
    return tree
