import random 
import streamlit as st
import math 
import folium

from streamlit_folium import st_folium

from data import (
    load_cities,
    build_tree,
)

from search import (
    build_search_index,
    search_city_candidates,
    city_display_name,
    get_city_priority, # 追加
)

from game import (
    calculate_distance,
    is_goal,
    make_move,
    calculate_route_efficiency,
)

# =========================================================
# UI STYLE
# =========================================================

st.markdown("""
<style>
.block-container { max-width: 1500px; padding-top: 1.5rem; }

.game-title { font-size: 2.4rem; font-weight: 550; letter-spacing: -0.04em; margin-bottom: 0; }
.game-subtitle { color: #777; font-size: 0.8rem; letter-spacing: 0.18em; margin-bottom: 1.2rem; }

.card { border: 1px solid rgba(128,128,128,0.25); border-radius: 14px; padding: 1rem 1.1rem; margin-bottom: 0.8rem; background: rgba(128,128,128,0.04); }
.card-label { font-size: 0.72rem; font-weight: 700; color: #777; letter-spacing: 0.1em; margin-bottom: 0.25rem; }
.city-name { font-size: 1.45rem; font-weight: 750; line-height: 1.2; }
.city-country { color: #777; font-size: 0.82rem; margin-top: 0.2rem; }

.score-card { border: 2px solid rgba(90,150,255,0.45); border-radius: 14px; padding: 0.45rem 0.8rem; text-align: center; background: rgba(90,150,255,0.05); }
.score-label { font-size: 0.65rem; font-weight: 700; color: #777; letter-spacing: 0.08em; }
.score-value { font-size: 1.65rem; font-weight: 800; font-variant-numeric: tabular-nums; color: #333;}

.section-label { font-size: 0.72rem; font-weight: 750; color: #777; letter-spacing: 0.12em; margin-bottom: 0.35rem; }
.hero { text-align: left; padding: 2.2rem 1rem 1rem; }
.hero-title { font-size: 3.1rem; font-weight: 550; letter-spacing: -0.05em; }
.hero-text { color: #777; font-size: 1rem; line-height: 1.8; }
.result-title { text-align: center; font-size: 2.7rem; font-weight: 850; margin: 1rem 0 1.3rem; }

/* ---- Game mode value (main / result screens) ---- */
.mode-value { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; margin-top: -0.2rem; }
.mode-tagline { color: #777; font-size: 0.85rem; margin-top: 0.1rem; margin-bottom: 0.6rem; }

/* ---- Help tooltip "?" bubble ---- */
.help-tip { cursor: help; color: #888; font-size: 0.72rem; border: 1px solid #bbb; border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center; width: 15px; height: 15px;
            margin-left: 6px; vertical-align: middle; }

/* ---- Route timeline (history box) ---- */
.route-box { border: 1px solid rgba(128,128,128,0.25); border-radius: 14px; padding: 1rem 1.2rem;
             max-height: 260px; overflow-y: auto; background: rgba(128,128,128,0.03); }
.tl-node { display: flex; align-items: center; gap: 10px; padding: 2px 0; }
.tl-dot { width: 13px; height: 13px; border-radius: 50%; flex-shrink: 0; }
.tl-dot.gray { background: #c7cbd1; }
.tl-dot.current { background: #22c55e; box-shadow: 0 0 0 4px rgba(34,197,94,0.15); }
.tl-dot.goal { background: #ef4444; }
.tl-city { font-weight: 700; font-size: 0.98rem; }
.tl-gap { display: flex; align-items: center; gap: 10px; height: 22px; padding-left: 1px; }
.tl-line { width: 2px; height: 100%; background: #d7d7d7; margin-left: 5px; }
.tl-line.dashed { width: 0; height: 100%; border-left: 2px dashed #cfcfcf; margin-left: 5px; background: none; }
.tl-km { font-size: 0.7rem; color: #999; }

/* ---- Buttons: primary = green (START / MOVE / Play Again) ---- */
.stButton>button[kind="primary"] { background-color: #22c55e !important; border-color: #22c55e !important; color: #fff !important; }
.stButton>button[kind="primary"]:hover { background-color: #16a34a !important; border-color: #16a34a !important; }
.stButton>button[kind="primary"]:disabled { background-color: #d8dbe0 !important; border-color: #d8dbe0 !important; color: #9aa0a8 !important; }

/* ---- Game-mode segmented buttons: highlight "Distance" in blue ---- */
div[class*="st-key-mode_distance_wrap"] button[kind="primary"] { background-color: #5b8def !important; border-color: #5b8def !important; }
div[class*="st-key-mode_distance_wrap"] button[kind="primary"]:hover { background-color: #4a76d4 !important; border-color: #4a76d4 !important; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# Data
# =========================================================

@st.cache_data(show_spinner="GeoNamesの都市データを読み込んでいます...")
def get_cities():
    return load_cities()

@st.cache_resource(show_spinner="検索システムを構築しています...")
def get_search_system(cities):
    search_index = build_search_index(cities)
    tree = build_tree(cities)
    return search_index, tree

cities = get_cities()
search_index, tree = get_search_system(cities)

@st.cache_data(show_spinner="ランダムモード用の大都市データを準備中...")
def get_major_city_indices(_cities):
    """
    ランダムスタートで無名すぎる都市が選ばれないよう、
    優先度（人口や首都などの属性）が高い上位300都市のインデックスを抽出します。
    """
    priorities = _cities.apply(get_city_priority, axis=1)
    return priorities.nlargest(300).index
    
# =========================================================
# Session State & Helper Functions
# =========================================================

DEFAULT_STATE = {
    "game_started": False,
    "game_finished": False,
    "game_result": None,
    "game_mode": "Distance",  # 現在はDistanceモードのみ実装
    "start_city": None,
    "goal_city": None,
    "current_city": None,
    "visited_cities": [],
    "total_distance": 0.0,
    "max_distance": 100.0,
    "last_move_distance": None,
    "start_candidates": [],
    "goal_candidates": [],
    "start_selected": None,
    "goal_selected": None,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = [] if isinstance(value, list) else value

def reset_game():
    """ゲームを初期化してスタート画面に戻る"""
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = [] if isinstance(value, list) else value

def play_again():
    """同じSTARTとGOALの設定を引き継いで再挑戦する"""
    st.session_state.game_started = True
    st.session_state.game_finished = False
    st.session_state.game_result = None
    st.session_state.current_city = st.session_state.start_city
    st.session_state.visited_cities = [st.session_state.start_city]
    st.session_state.total_distance = 0.0
    st.session_state.last_move_distance = None

def render_route_timeline(visited_cities, goal_city=None, finished=False):
    """
    ルート履歴をタイムライン形式のHTMLで生成する。
    - 通過済み都市：グレーの丸
    - 現在地（最後に訪れた都市）：グリーンの丸
    - ゴール（未到達時のプレビュー）：レッドの丸＋点線
    """
    parts = []
    n = len(visited_cities)

    for i, city in enumerate(visited_cities):
        is_last = (i == n - 1)

        if i > 0:
            prev = visited_cities[i - 1]
            dist = calculate_distance(prev, city)
            parts.append(
                f'<div class="tl-gap"><span class="tl-line solid"></span>'
                f'<span class="tl-km">{dist:.1f}km</span></div>'
            )

        dot_class = "current" if is_last else "gray"
        parts.append(
            f'<div class="tl-node"><span class="tl-dot {dot_class}"></span>'
            f'<span class="tl-city">{city["name"]}</span></div>'
        )

    if not finished and goal_city is not None:
        parts.append('<div class="tl-gap"><span class="tl-line dashed"></span></div>')
        parts.append(
            f'<div class="tl-node"><span class="tl-dot goal"></span>'
            f'<span class="tl-city">{goal_city["name"]}</span></div>'
        )

    return '<div class="route-box">' + "".join(parts) + '</div>'


@st.dialog("ルート確認")
def confirm_tutorial(route):
    """チュートリアル選択時のポップアップとスタート処理"""
    st.markdown("以下の設定でゲームを開始しますか？")
    st.markdown(f"### {route['title']}")
    st.markdown(f"**ルート**: {route['desc']}")
    st.markdown(f"**最大移動距離**: {route['max_distance']} km")
    
    st.write("")
    if st.button("ゲームスタート", type="primary", use_container_width=True):
        # 確実に見つけるため完全一致 (fuzzy=False) で都市データを取得
        start_cands = search_city_candidates(cities, search_index, route["start"], fuzzy=False)
        goal_cands = search_city_candidates(cities, search_index, route["goal"], fuzzy=False)
        
        if start_cands and goal_cands:
            st.session_state.game_started = True
            st.session_state.game_finished = False
            st.session_state.game_result = None
            st.session_state.start_city = start_cands[0]["city"]
            st.session_state.goal_city = goal_cands[0]["city"]
            st.session_state.current_city = start_cands[0]["city"]
            st.session_state.visited_cities = [start_cands[0]["city"]]
            st.session_state.total_distance = 0.0
            st.session_state.max_distance = float(route["max_distance"])
            st.session_state.last_move_distance = None
            st.rerun()
        else:
            st.error("都市データの検索に失敗しました。")


# =========================================================
# Map
# =========================================================

def create_map(visited_cities, start_city, goal_city, current_city, max_distance):
    MAPTILER_API_KEY = "bdBZZiwFtIdbj11AY3CE"
    tiles_url = f"https://api.maptiler.com/maps/aquarelle-v4/{{z}}/{{x}}/{{y}}.png?key={MAPTILER_API_KEY}"
    
    # 座標補正ヘルパー関数：基準となる経度(ref_lon)から最短距離になるように目的の経度(target_lon)を補正する
    def get_corrected_lon(target_lon, ref_lon):
        diff = (target_lon - ref_lon + 180) % 360 - 180
        return ref_lon + diff

    # スタート地点を基準に、ルート全体の連続した経度を計算する
    base_lon = float(start_city["longitude"])
    corrected_route_points = []
    prev_lon = base_lon
    
    for city in visited_cities:
        lat = float(city["latitude"])
        lon = get_corrected_lon(float(city["longitude"]), prev_lon)
        corrected_route_points.append([lat, lon])
        prev_lon = lon

    # 現在地（リストの最後）の補正済み経度
    current_corrected_lon = corrected_route_points[-1][1] if corrected_route_points else base_lon

    # 地図の初期化（中心を補正済みの現在地にする）
    m = folium.Map(
        location=[float(current_city["latitude"]), current_corrected_lon],
        zoom_start=6,
        tiles=tiles_url,
        attr='&copy; <a href="https://www.maptiler.com/copyright/" target="_blank">MapTiler</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap contributors</a>'
    )

    # 現在地の円（移動可能領域）
    folium.Circle(
        location=[float(current_city["latitude"]), current_corrected_lon],
        radius=max_distance * 1000, 
        color="orange", weight=2, fill=True, fill_color="orange", fill_opacity=0.3,
        tooltip=f"移動可能エリア (MAX {max_distance:.0f} km)"
    ).add_to(m)

    # 補正済みの直線ルートを描画
    if len(corrected_route_points) >= 2:
        folium.PolyLine(corrected_route_points, weight=4, opacity=0.8, tooltip="移動ルート").add_to(m)

    # STARTマーカー
    folium.Marker(
        [float(start_city["latitude"]), base_lon],
        tooltip="START", popup=f"START<br>{start_city['name']}",
        icon=folium.Icon(color="orange", icon="play"),
    ).add_to(m)

    # ★ GOALマーカーの補正（現在地を基準に、日付変更線の向こう側へ配置する）
    g_lat = float(goal_city["latitude"])
    g_lon = get_corrected_lon(float(goal_city["longitude"]), current_corrected_lon)
    
    folium.Marker(
        [g_lat, g_lon],
        tooltip="GOAL", popup=f"GOAL<br>{goal_city['name']}",
        icon=folium.Icon(color="red", icon="flag"),
    ).add_to(m)

    # 中継都市の小マーカー
    for i, (city, corrected_pos) in enumerate(zip(visited_cities, corrected_route_points)):
        if city["geonameid"] == start_city["geonameid"] or city["geonameid"] == current_city["geonameid"]:
            continue
        folium.CircleMarker(
            corrected_pos,
            radius=5, tooltip=f"{i + 1}. {city['name']}", fill=True,
        ).add_to(m)

    # CURRENTマーカー
    folium.Marker(
        [float(current_city["latitude"]), current_corrected_lon],
        tooltip="CURRENT", popup=f"CURRENT<br>{current_city['name']}",
        icon=folium.Icon(color="green", icon="location-arrow"),
    ).add_to(m)

    # カメラのズーム枠を、補正済みのルートとゴールに合わせて最適化
    bounds_points = corrected_route_points.copy()
    bounds_points.append([g_lat, g_lon])
    if len(bounds_points) >= 2:
        m.fit_bounds(bounds_points)

    return m


# =========================================================
# SETUP SCREEN
# =========================================================

# ---------------------------------------------------------
# ランダムモード用の地域マッピング
# ---------------------------------------------------------
REGION_MAP = {
    "指定なし": None,
    "アジア": ["JP", "CN", "KR", "KP", "TW", "HK", "IN", "ID", "TH", "VN", "MY", "PH", "SG"],
    "北アメリカ": ["US", "CA", "MX", "CU", "JM", "PA", "CR"],
    "ヨーロッパ": ["GB", "FR", "DE", "IT", "ES", "NL", "BE", "CH", "AT", "SE", "NO", "DK", "FI", "PL", "UA", "IE", "PT", "GR"],
    "南アメリカ": ["BR", "AR", "CO", "CL", "PE", "VE", "EC", "UY"],
    "オセアニア": ["AU", "NZ", "PG"],
    "アフリカ": ["ZA", "EG", "NG", "KE", "MA", "DZ", "ET", "GH", "TZ"],
    "中東": ["AE", "SA", "IL", "TR", "IR", "IQ", "QA", "KW", "OM", "SY", "LB", "JO"]
}

#モード選択(rondon, freeplay, turtorial)
if not st.session_state.game_started:
    st.markdown('<div class="hero">', unsafe_allow_html=True)
    # ロゴ画像を表示
    st.image("city-chain.png", width=350) 
    st.markdown('</div>', unsafe_allow_html=True)

    # モード切り替えをサブ機能に
    st.markdown(
        '<div class="section-label">GAME MODE'
        '<span class="help-tip" title="現在はDistanceモードのみ実装されています。">?</span></div>',
        unsafe_allow_html=True,
    )
    #ゲームモード（Time, Distance, Visit）は廃止（1つのモードに統合）
    # mc1, mc2, mc3 = st.columns(3)
    # with mc1:
    #     st.button("Time", use_container_width=True, disabled=True, key="mode_time_btn")
    # with mc2:
    #     with st.container(key="mode_distance_wrap"):
    #         st.button("Distance", use_container_width=True, type="primary", key="mode_distance_btn")
    # with mc3:
    #     st.button("Visit", use_container_width=True, disabled=True, key="mode_visit_btn")
    # st.write("")

    # ★ メインシステムとサブシステムをタブで分割
    tab_random, tab_custom, tab_tutorial = st.tabs([
        "Rondam Route", 
        "Free Play", 
        "Tutorial"
    ])

  # -------------------------------
    # タブ1：ランダムスタート（メイン）
    # -------------------------------
    with tab_random:
        st.markdown("Rondam Route")
        st.write("世界中の主要都市からランダムに選ばれたスタートとゴールを繋ぎましょう！")
        
        # CSVデータから存在する国名(country)のリストを自動抽出してソート
        available_countries = [c for c in cities["country"].unique() if isinstance(c, str) and c.strip()]
        available_countries.sort()
        country_options = ["指定なし"] + available_countries
        
        # 難易度・地域・国を3カラムで配置
        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            difficulty = st.selectbox("難易度", ["Easy (簡単)", "Normal (普通)", "Hard (難しい)"], index=1)
        with r_col2:
            region_sel = st.selectbox("地域選択", list(REGION_MAP.keys()), index=0)
        with r_col3:
            country_sel = st.selectbox("国選択", country_options, index=0)
        
        st.write("")
        if st.button("START", type="primary", use_container_width=True, key="btn_random_start"):
            major_indices = get_major_city_indices(cities)
            filtered_cities = cities.loc[major_indices]
            
            # 1. 地域で絞り込み (country_codeで判定)
            if region_sel != "指定なし":
                filtered_cities = filtered_cities[filtered_cities["country_code"].isin(REGION_MAP[region_sel])]
                
            # 2. 国で絞り込み (自動抽出したcountryカラムで判定)
            if country_sel != "指定なし":
                filtered_cities = filtered_cities[filtered_cities["country"] == country_sel]
            
            # 条件に合う都市が少なすぎる場合のエラーチェック
            if len(filtered_cities) < 2:
                st.error("⚠️ 地域または国のどちらか一方を選択してください。")
            # 条件に合う都市が少なすぎる場合のエラーチェック
            if len(filtered_cities) < 2:
                st.error("⚠️ 地域または国のどちらか一方を選択してください。")
            else:
                max_attempts = 100
                valid_pair_found = False
                
                # 25km以上離れたペアが見つかるまで最大100回再抽選する
                for _ in range(max_attempts):
                    # 絞り込んだリストからランダムに2つのインデックスを取得
                    rand_indices = random.sample(list(filtered_cities.index), 2)
                    
                    start_city = filtered_cities.loc[rand_indices[0]]
                    goal_city = filtered_cities.loc[rand_indices[1]]
                    
                    # スタートとゴールの直線距離を計算
                    dist = calculate_distance(start_city, goal_city)
                    
                    # 基本条件：距離が50km以上
                    is_valid = (dist >= 25.0)
                    
                    # 追加条件：地域指定のみの場合、異なる国どうしのペアにする
                    if region_sel != "指定なし" and country_sel == "指定なし":
                        if start_city["country_code"] == goal_city["country_code"]:
                            is_valid = False

                    # 追加条件：地域指定と国指定がどちらも指定されていない場合、異なる国どうしのペアにする
                    if region_sel == "指定なし" and country_sel == "指定なし":
                        if start_city["country_code"] == goal_city["country_code"]:
                            is_valid = False
                            
                    if is_valid:
                        valid_pair_found = True
                        break
                
                if not valid_pair_found:
                    st.error("⚠️ 指定された条件内で、50km以上離れた都市のペアが見つかりませんでした。条件を広げてください。")
                else:
                    # 距離と難易度に応じた MAX DISTANCE の算出
                    if "Easy" in difficulty:
                        calculated_max = max(100.0, dist / 2.5)
                    elif "Normal" in difficulty:
                        calculated_max = max(50.0, dist / 3.5)
                    else:
                        calculated_max = max(30.0, dist / 8.0)
                    
                    # 10km単位に丸める
                    calculated_max = round(calculated_max / 10.0) * 10.0
                    if calculated_max < 10.0:
                        calculated_max = 10.0

                    st.session_state.game_started = True
                    st.session_state.game_finished = False
                    st.session_state.game_result = None
                    st.session_state.start_city = start_city
                    st.session_state.goal_city = goal_city
                    st.session_state.current_city = start_city
                    st.session_state.visited_cities = [start_city]
                    st.session_state.total_distance = 0.0
                    st.session_state.max_distance = float(calculated_max)
                    st.session_state.last_move_distance = None
                    st.rerun()

    # -------------------------------
    # タブ2：Free Play（サブ）
    # -------------------------------
    with tab_custom:
        st.markdown("Free Play")
        st.write("好きな都市を手動で設定してプレイできます。")
        
        # ---- START CITY ----
        st.write("**Start City**")
        with st.container(border=True):
            start_query = st.text_input("Start City", placeholder="例：Tokyo / 東京", key="start_query", label_visibility="collapsed")
            if start_query.strip():
                start_candidates = search_city_candidates(cities, search_index, start_query, fuzzy=True)
                if start_candidates:
                    st.caption("📍 もしかして")
                    start_options = {item["city"]["geonameid"]: item for item in start_candidates}
                    start_selected_id = st.selectbox(
                        "START CITYを選択", 
                        options=list(start_options.keys()),
                        format_func=lambda x: city_display_name(start_options[x]["city"]), 
                        key="start_selection", label_visibility="collapsed"
                    )
                    st.session_state.start_selected = start_options[start_selected_id]["city"]
                else:
                    st.warning("都市が見つかりません。")
                    st.session_state.start_selected = None
            else:
                st.session_state.start_selected = None

        # ---- GOAL CITY ----
        st.write("**Goal City**")
        with st.container(border=True):
            goal_query = st.text_input("Goal City", placeholder="例：Osaka / 大阪", key="goal_query", label_visibility="collapsed")
            if goal_query.strip():
                goal_candidates = search_city_candidates(cities, search_index, goal_query, fuzzy=True)
                if goal_candidates:
                    st.caption("📍 もしかして")
                    goal_options = {item["city"]["geonameid"]: item for item in goal_candidates}
                    goal_selected_id = st.selectbox(
                        "GOAL CITYを選択", 
                        options=list(goal_options.keys()),
                        format_func=lambda x: city_display_name(goal_options[x]["city"]), 
                        key="goal_selection", label_visibility="collapsed"
                    )
                    st.session_state.goal_selected = goal_options[goal_selected_id]["city"]
                else:
                    st.warning("都市が見つかりません。")
                    st.session_state.goal_selected = None
            else:
                st.session_state.goal_selected = None

        st.write("")
        max_distance_custom = st.number_input("最大移動距離 MAX DISTANCE (km)", min_value=1.0, max_value=5000.0, value=100.0, step=10.0)
        st.write("")

        ready_to_start = (st.session_state.start_selected is not None and st.session_state.goal_selected is not None)

        if st.button("START", use_container_width=True, type="primary", disabled=not ready_to_start, key="btn_custom_start"):
            start_city = st.session_state.start_selected
            goal_city = st.session_state.goal_selected

            if start_city["geonameid"] == goal_city["geonameid"]:
                st.error("STARTとGOALは別の都市にしてください。")
            else:
                st.session_state.game_started = True
                st.session_state.game_finished = False
                st.session_state.game_result = None
                st.session_state.start_city = start_city
                st.session_state.goal_city = goal_city
                st.session_state.current_city = start_city
                st.session_state.visited_cities = [start_city]
                st.session_state.total_distance = 0.0
                st.session_state.max_distance = float(max_distance_custom)
                st.session_state.last_move_distance = None
                st.rerun()


    # -------------------------------
    # タブ3：Tutorial（サブ）
    # -------------------------------
    with tab_tutorial:
        st.markdown("Turorial")
        st.write("クリックですぐにゲームを開始できるおすすめルートです。")
        
        TUTORIAL_ROUTES = [
            {"title": "🔰 短距離", "desc": "東京 - 大阪", "start": "Tokyo", "goal": "Osaka", "max_distance": 100.0},
            {"title": "✈️ 中距離", "desc": "ロンドン - イスタンブル", "start": "London", "goal": "Istanbul", "max_distance": 600.0},
            {"title": "🌎 長距離", "desc": "ニューヨーク - ロサンゼルス", "start": "New York", "goal": "Los Angeles", "max_distance": 1000.0},
            {"title": "🚀 超長距離", "desc": "東京 - ロンドン", "start": "Tokyo", "goal": "London", "max_distance": 3000.0},
        ]
        
        for i in range(0, len(TUTORIAL_ROUTES), 2):
            c1, c2 = st.columns(2)
            with c1:
                route = TUTORIAL_ROUTES[i]
                with st.container(border=True):
                    st.markdown(f"**{route['title']}**")
                    st.markdown(f"<div style='font-size:0.85rem; color:#666;'>{route['desc']}<br>MAX: {route['max_distance']} km</div>", unsafe_allow_html=True)
                    st.write("")
                    if st.button("選択", key=f"tut_{i}", use_container_width=True):
                        confirm_tutorial(route)
            
            with c2:
                if i + 1 < len(TUTORIAL_ROUTES):
                    route = TUTORIAL_ROUTES[i+1]
                    with st.container(border=True):
                        st.markdown(f"**{route['title']}**")
                        st.markdown(f"<div style='font-size:0.85rem; color:#666;'>{route['desc']}<br>MAX: {route['max_distance']} km</div>", unsafe_allow_html=True)
                        st.write("")
                        if st.button("選択", key=f"tut_{i+1}", use_container_width=True):
                            confirm_tutorial(route)

    st.divider()
    st.caption(f"都市データ：{len(cities):,} cities")
    st.stop()


# =========================================================
# GAME VARIABLES
# =========================================================

start_city = st.session_state.start_city
goal_city = st.session_state.goal_city
current_city = st.session_state.current_city
visited_cities = st.session_state.visited_cities
total_distance = st.session_state.total_distance
max_distance = st.session_state.max_distance

route_efficiency = calculate_route_efficiency(start_city, goal_city, current_city, total_distance)
ideal_distance = calculate_distance(start_city, goal_city)

# =========================================================
# HEADER (with hamburger settings menu)
# =========================================================

h_col1, h_col2 = st.columns([9, 1])
with h_col1:
    # テキストの代わりに画像を表示（widthはヘッダーに合わせて少し小さめに）
    st.image("city-chain.png", width=250)
with h_col2:
    with st.popover("Setting", use_container_width=True):
        if st.button("🔄 Restart", use_container_width=True):
            play_again()
            st.rerun()
        if st.button("⏹️ Exit the Game", use_container_width=True):
            reset_game()
            st.rerun()

st.divider()

# =========================================================
# RESULT SCREEN
# =========================================================

if st.session_state.game_finished:
    result = st.session_state.game_result


# 左端に「spacer」として 0.1 の余白カラムを追加します
    # ※元の比率が [0.82, 1.7] だった場合は [0.1, 0.82, 1.7] にしてください
    r_left, r_right = st.columns([1, 1], gap="large")

    with r_left:
        if result == "CLEAR":
            #st.markdown("Result")
            
            #st.markdown('<div class="section-label">GAME MODE</div>', unsafe_allow_html=True)
            # st.markdown(
            #     f'<div class="mode-value" style="margin-bottom: 1.5rem;">{st.session_state.game_mode}</div>',
            #     unsafe_allow_html=True,
            # )

            # ランク判定
            if route_efficiency >= 95.0:
                rank = "S (Perfect!)"
            elif route_efficiency >= 80.0:
                rank = "A (Excellent)"
            elif route_efficiency >= 60.0:
                rank = "B (Good)"
            else:
                rank = "C (Bad)"

            eff_col, spacer, rank_col = st.columns([1, 0.5, 1])
            with eff_col:
                st.markdown(
                    f"""
                    <div class="score-card">
                        <div class="score-label">ROUTE EFFICIENCY</div>
                        <div class="score-value">{route_efficiency:.1f}%</div>
                    </div>
                    """, unsafe_allow_html=True,
                )
            with rank_col:
                st.markdown('<div class="section-label">RANK</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="mode-value">{rank}</div>', unsafe_allow_html=True)

            st.write("")
            diff = total_distance - ideal_distance
            spacer, s1, s2, s3 = st.columns([0.1,1,1,1])
            with s1:
                st.markdown(
                    f"""
                    <div class="section-label">TOTAL DISTANCE</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #333; margin-top: -0.2rem;">{total_distance:.0f} km</div>
                    """, 
                    unsafe_allow_html=True
                )
            with s2:
                st.markdown(
                    f"""
                    <div class="section-label">IDEAL DISTANCE</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #333; margin-top: -0.2rem;">{ideal_distance:.0f} km</div>
                    """, 
                    unsafe_allow_html=True
                )
            with s3:
                st.markdown(
                    f"""
                    <div class="section-label">DIFFERENCE</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #333; margin-top: -0.2rem;">{diff:+.0f} km</div>
                    """, 
                    unsafe_allow_html=True
                )
            st.write("")
            b1, b2 = st.columns(2)
            with b1:
                if st.button("⏩️ Try Another Route", use_container_width=True, type="primary"):
                    reset_game()
                    st.rerun()
            with b2:
                if st.button("🔄 Play Again", use_container_width=True):
                    play_again()
                    st.rerun()

        game_map = create_map(visited_cities, start_city, goal_city, current_city, max_distance)
        st_folium(game_map, width=None, height=420, returned_objects=[])

    with r_right:
        st.write("")
        st.markdown('<div class="section-label">ROUTE HISTORY</div>', unsafe_allow_html=True)
        st.markdown(render_route_timeline(visited_cities, finished=True), unsafe_allow_html=True)

    st.stop()

# =========================================================
# MAIN GAME AREA
# =========================================================

current_distance_to_goal = calculate_distance(current_city, goal_city)

left, right = st.columns([0.82, 1.7], gap="large")

with left:
    # ---- GAME MODE ----
    st.markdown('<div class="section-label">GAME MODE</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mode-value">{st.session_state.game_mode}</div>', unsafe_allow_html=True)
    st.markdown('<div class="mode-tagline">最短距離でGoalを目指せ！</div>', unsafe_allow_html=True)

    # ---- ROUTE HISTORY (timeline) ----
    st.markdown(
        render_route_timeline(visited_cities, goal_city, finished=False),
        unsafe_allow_html=True,
    )

    st.write("")

    ## ---- WHERE TO NEXT ----
    st.markdown('<div class="section-label">WHERE TO NEXT?</div>', unsafe_allow_html=True)
    
    # 距離に応じてGoogle Mapsのズームレベルを最適化（距離が大きいほど広域を表示）
    zoom_level = max(3, int(14 - math.log2(max_distance)))
    gmaps_url = f"https://www.google.com/maps/@{current_city['latitude']},{current_city['longitude']},{zoom_level}z"

    # キャプションとヒントボタンを横並びに配置
    col_cap, col_hint = st.columns([7, 3], vertical_alignment="bottom")
    with col_cap:
        st.caption(f"最大 {max_distance:.0f} km 以内の都市へ移動できます。")
    with col_hint:
        st.link_button("周辺を調べる", gmaps_url, use_container_width=True, help="Google Mapsを開いてヒントを探します")

    next_query = st.text_input("次の都市", placeholder="例：Yokohama / よこはま / 横浜", label_visibility="collapsed", key="next_city_input")

    if next_query.strip():
        exact_candidates = search_city_candidates(
            cities, search_index, next_query,
            current_city=current_city, max_distance=max_distance,
            calculate_distance_func=calculate_distance,
            fuzzy=False, tree=tree,
        )

        if exact_candidates:
            if len(exact_candidates) == 1:
                selected_city = exact_candidates[0]["city"]
                selected_distance = exact_candidates[0]["distance"]
                st.success(f"📍 {city_display_name(selected_city)}")
                st.caption(f"現在地から {selected_distance:.1f} km")

                if st.button("MOVE", use_container_width=True, type="primary", key="exact_move"):
                    new_current, new_total, new_visited, move_distance = make_move(current_city, selected_city, total_distance, visited_cities)
                    st.session_state.current_city = new_current
                    st.session_state.total_distance = new_total
                    st.session_state.visited_cities = new_visited
                    st.session_state.last_move_distance = move_distance

                    if is_goal(new_current, goal_city):
                        st.session_state.game_finished = True
                        st.session_state.game_result = "CLEAR"
                    st.rerun()
            # app.py の MAIN GAME AREA 内、「同名の都市があります」の分岐部分も同様に書き換えます

            else:
                st.info("同名の都市があります。移動先を選択してください。")
                
                # インデックスではなく geonameid ベースに修正
                exact_options = {item["city"]["geonameid"]: item for item in exact_candidates}
                
                selected_id = st.selectbox(
                    "移動先", 
                    options=list(exact_options.keys()), 
                    format_func=lambda x: f"{city_display_name(exact_options[x]['city'])} — {exact_options[x]['distance']:.1f} km", 
                    key="exact_city_selection"
                )
                selected_city = exact_options[selected_id]["city"]

                if st.button("MOVE", use_container_width=True, type="primary", key="exact_multiple_move"):
                    # 以降の処理は既存のまま
                    new_current, new_total, new_visited, move_distance = make_move(current_city, selected_city, total_distance, visited_cities)
                    st.session_state.current_city = new_current
                    st.session_state.total_distance = new_total
                    st.session_state.visited_cities = new_visited
                    st.session_state.last_move_distance = move_distance

                    if is_goal(new_current, goal_city):
                        st.session_state.game_finished = True
                        st.session_state.game_result = "CLEAR"
                    st.rerun()

        else:
            fuzzy_nearby = search_city_candidates(
                cities, search_index, next_query,
                current_city=current_city, max_distance=max_distance,
                calculate_distance_func=calculate_distance,
                fuzzy=True, tree=tree,
            )

            if not fuzzy_nearby:
                st.error("❌ 指定した距離内に該当する都市が見つかりません。")
            else:
                suggestion = fuzzy_nearby[0]
                suggestion_city = suggestion["city"]
                suggestion_distance = suggestion["distance"]

                st.info(f"💡 もしかして **{city_display_name(suggestion_city)}** ですか？")
                st.caption(f"現在地から {suggestion_distance:.1f} km")
                confirm = st.radio("この都市に移動しますか？", ["はい", "いいえ"], horizontal=True, key="fuzzy_confirm")

                if confirm == "はい":
                    if st.button("MOVE", use_container_width=True, type="primary", key="fuzzy_move"):
                        new_current, new_total, new_visited, move_distance = make_move(current_city, suggestion_city, total_distance, visited_cities)
                        st.session_state.current_city = new_current
                        st.session_state.total_distance = new_total
                        st.session_state.visited_cities = new_visited
                        st.session_state.last_move_distance = move_distance

                        if is_goal(new_current, goal_city):
                            st.session_state.game_finished = True
                            st.session_state.game_result = "CLEAR"
                        st.rerun()

    if st.session_state.last_move_distance is not None:
        st.success(f"移動距離：{st.session_state.last_move_distance:.1f} km")

with right:
    # ---- STATS ROW ----
    s1, spacer, s2, s3 = st.columns([1, 0.4, 1, 1])
    with s1:
        st.markdown(
            f"""
            <div class="score-card">
                <div class="score-label">ROUTE EFFICIENCY</div>
                <div class="score-value">{route_efficiency:.1f}%</div>
            </div>
            """, unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            f"""
            <div class="section-label">TOTAL DISTANCE</div>
            <div style="font-size: 1.8rem; font-weight: 700; color: #333; margin-top: -0.2rem;">{total_distance:.1f} km</div>
            """, 
            unsafe_allow_html=True
        )
    with s3:
        st.markdown(
            f"""
            <div class="section-label">DISTANCE TO GOAL</div>
            <div style="font-size: 1.8rem; font-weight: 700; color: #333; margin-top: -0.2rem;">{current_distance_to_goal:.1f} km</div>
            """, 
            unsafe_allow_html=True
        )

    st.write("")

    # ---- MAP ----
    game_map = create_map(visited_cities, start_city, goal_city, current_city, max_distance)
    st_folium(game_map, width=None, height=560, returned_objects=[])