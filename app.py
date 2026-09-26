import time

import streamlit as st
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
)

from game import (
    calculate_distance,
    get_remaining_time,
    format_time,
    is_goal,
    make_move,
)


# =========================================================
# UI STYLE
# =========================================================

st.markdown("""
<style>
.block-container { max-width: 1500px; padding-top: 1.5rem; }
.game-title { font-size: 2.4rem; font-weight: 800; letter-spacing: -0.04em; margin-bottom: 0; }
.game-subtitle { color: #777; font-size: 0.8rem; letter-spacing: 0.18em; margin-bottom: 1.2rem; }
.card { border: 1px solid rgba(128,128,128,0.25); border-radius: 14px; padding: 1rem 1.1rem; margin-bottom: 0.8rem; background: rgba(128,128,128,0.04); }
.card-label { font-size: 0.72rem; font-weight: 700; color: #777; letter-spacing: 0.1em; margin-bottom: 0.25rem; }
.city-name { font-size: 1.45rem; font-weight: 750; line-height: 1.2; }
.city-country { color: #777; font-size: 0.82rem; margin-top: 0.2rem; }
.timer-card { border: 2px solid rgba(255,90,90,0.45); border-radius: 14px; padding: 0.45rem 0.8rem; text-align: center; background: rgba(255,90,90,0.05); }
.timer-label { font-size: 0.65rem; font-weight: 700; color: #777; letter-spacing: 0.08em; }
.timer-value { font-size: 1.65rem; font-weight: 800; font-variant-numeric: tabular-nums; }
.section-label { font-size: 0.72rem; font-weight: 750; color: #777; letter-spacing: 0.12em; margin-bottom: 0.35rem; }
.hero { text-align: left; padding: 2.2rem 1rem 1rem; }
.hero-title { font-size: 3.1rem; font-weight: 550; letter-spacing: -0.05em; }
.hero-text { color: #777; font-size: 1rem; line-height: 1.8; }
.result-title { text-align: center; font-size: 2.7rem; font-weight: 850; margin: 1rem 0 1.3rem; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# Game settings & Data
# =========================================================

GAME_TIME_LIMIT = 10 * 60

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


# =========================================================
# Session State
# =========================================================

DEFAULT_STATE = {
    "game_started": False,
    "game_finished": False,
    "game_result": None,
    "start_city": None,
    "goal_city": None,
    "current_city": None,
    "visited_cities": [],
    "total_distance": 0.0,
    "start_time": None,
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
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = [] if isinstance(value, list) else value


# =========================================================
# Map
# =========================================================

def create_map(visited_cities, start_city, goal_city, current_city):
    m = folium.Map(
        location=[float(current_city["latitude"]), float(current_city["longitude"])],
        zoom_start=6,
        tiles="Esri.WorldImagery",
    )

    if len(visited_cities) >= 2:
        route_points = [[float(c["latitude"]), float(c["longitude"])] for c in visited_cities]
        folium.PolyLine(route_points, weight=4, opacity=0.8, tooltip="移動ルート").add_to(m)

    folium.Marker(
        [float(start_city["latitude"]), float(start_city["longitude"])],
        tooltip="START",
        popup=f"START<br>{start_city['name']}",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    folium.Marker(
        [float(goal_city["latitude"]), float(goal_city["longitude"])],
        tooltip="GOAL",
        popup=f"GOAL<br>{goal_city['name']}",
        icon=folium.Icon(color="red", icon="flag"),
    ).add_to(m)

    for i, city in enumerate(visited_cities):
        if city["geonameid"] == start_city["geonameid"] or city["geonameid"] == current_city["geonameid"]:
            continue
        folium.CircleMarker(
            [float(city["latitude"]), float(city["longitude"])],
            radius=5, tooltip=f"{i + 1}. {city['name']}", fill=True,
        ).add_to(m)

    folium.Marker(
        [float(current_city["latitude"]), float(current_city["longitude"])],
        tooltip="CURRENT",
        popup=f"CURRENT<br>{current_city['name']}",
        icon=folium.Icon(color="orange", icon="location-arrow"),
    ).add_to(m)

    points = [[float(c["latitude"]), float(c["longitude"])] for c in list(visited_cities) + [start_city, goal_city, current_city]]
    if len(points) >= 2:
        m.fit_bounds(points)

    return m


# =========================================================
# SETUP SCREEN
# =========================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-title">🌏 The City Chain</div>
        <div class="hero-text">世界の都市を、決められた距離以内でつないで<br>STARTからGOALまでたどり着こう。</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.divider()

if not st.session_state.game_started:
    st.subheader("🎮 GAME SETTINGS")

    # START input
    start_query = st.text_input("START CITY", placeholder="例：Tokyo / 東京", key="start_query")
    if start_query.strip():
        start_candidates = search_city_candidates(cities, search_index, start_query, fuzzy=True)
        if start_candidates:
            st.session_state.start_candidates = start_candidates
            st.write("📍 START：もしかして")
            start_labels = [city_display_name(item["city"]) for item in start_candidates]
            start_selected = st.selectbox(
                "START CITYを選択", range(len(start_candidates)),
                format_func=lambda i: start_labels[i], key="start_selection"
            )
            st.session_state.start_selected = start_candidates[start_selected]["city"]
        else:
            st.warning("都市が見つかりません。")

    # GOAL input
    goal_query = st.text_input("GOAL CITY", placeholder="例：Osaka / 大阪", key="goal_query")
    if goal_query.strip():
        goal_candidates = search_city_candidates(cities, search_index, goal_query, fuzzy=True)
        if goal_candidates:
            st.session_state.goal_candidates = goal_candidates
            st.write("🎯 GOAL：もしかして")
            goal_labels = [city_display_name(item["city"]) for item in goal_candidates]
            goal_selected = st.selectbox(
                "GOAL CITYを選択", range(len(goal_candidates)),
                format_func=lambda i: goal_labels[i], key="goal_selection"
            )
            st.session_state.goal_selected = goal_candidates[goal_selected]["city"]
        else:
            st.warning("都市が見つかりません。")

    max_distance = st.number_input("MAX DISTANCE (km)", min_value=1.0, max_value=5000.0, value=100.0, step=10.0)
    st.divider()

    if st.button("🚀 GAME START", use_container_width=True):
        start_city = st.session_state.start_selected
        goal_city = st.session_state.goal_selected

        if start_city is None:
            st.error("START CITYを選択してください。")
            st.stop()
        if goal_city is None:
            st.error("GOAL CITYを選択してください。")
            st.stop()
        if start_city["geonameid"] == goal_city["geonameid"]:
            st.error("STARTとGOALは別の都市にしてください。")
            st.stop()

        st.session_state.game_started = True
        st.session_state.game_finished = False
        st.session_state.game_result = None
        st.session_state.start_city = start_city
        st.session_state.goal_city = goal_city
        st.session_state.current_city = start_city
        st.session_state.visited_cities = [start_city]
        st.session_state.total_distance = 0.0
        st.session_state.start_time = time.time()
        st.session_state.max_distance = float(max_distance)
        st.session_state.last_move_distance = None
        st.rerun()

    st.divider()
    st.info("STARTとGOALを入力すると、該当する都市の候補が表示されます。")
    st.caption(f"都市データ：{len(cities):,} cities")
    st.stop()


# =========================================================
# GAME VARIABLES & TIME
# =========================================================

start_city = st.session_state.start_city
goal_city = st.session_state.goal_city
current_city = st.session_state.current_city
visited_cities = st.session_state.visited_cities
total_distance = st.session_state.total_distance
max_distance = st.session_state.max_distance
start_time = st.session_state.start_time

remaining_time = get_remaining_time(start_time, GAME_TIME_LIMIT)

if remaining_time <= 0 and not st.session_state.game_finished:
    st.session_state.game_finished = True
    st.session_state.game_result = "TIME UP"
    st.rerun()


# =========================================================
# RESULT
# =========================================================

if st.session_state.game_finished:
    result = st.session_state.game_result

    if result == "CLEAR":
        st.success("🎉 GAME CLEAR!")
    else:
        st.error("⏰ TIME UP!")

    st.subheader("📊 GAME RESULT")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("START", start_city["name"])
    col2.metric("GOAL", goal_city["name"])
    col3.metric("TOTAL DISTANCE", f"{total_distance:.1f} km")
    col4.metric("VISITED", f"{len(visited_cities)} cities")
    st.divider()

    st.subheader("🗺️ ROUTE")
    for i, city in enumerate(visited_cities):
        if i == 0:
            st.write(f"🟢 {city['name']}")
        else:
            previous = visited_cities[i - 1]
            distance = calculate_distance(previous, city)
            st.write(f"↓ {distance:.1f} km")
            st.write(f"📍 {city['name']}")

    game_map = create_map(visited_cities, start_city, goal_city, current_city)
    st_folium(game_map, width=None, height=600, returned_objects=[])
    st.divider()

    if st.button("🔄 NEW GAME", use_container_width=True):
        reset_game()
        st.rerun()
    st.stop()


# =========================================================
# MAIN GAME AREA
# =========================================================

current_distance_to_goal = calculate_distance(current_city, goal_city)

# TOP STATUS
m1, m2, m3, m4 = st.columns([1.35, 1.35, 1.2, 1.15])
m1.metric("📍 Start City", start_city["name"])
m2.metric("🎯 DISTANCE TO GOAL", f"{current_distance_to_goal:.1f} km")
m3.metric("📏 TOTAL DISTANCE", f"{total_distance:.1f} km")
m4.markdown(
    f"""
    <div class="timer-card">
        <div class="timer-label">TIME REMAINING</div>
        <div class="timer-value">{format_time(remaining_time)}</div>
    </div>
    """, unsafe_allow_html=True,
)
st.divider()

left, right = st.columns([0.82, 1.7], gap="large")

with left:
    st.markdown('<div class="section-label">CURRENT CITY</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="card">
            <div class="city-name">🟠 {current_city["name"]}</div>
            <div class="city-country">{current_city["country"]} ({current_city["country_code"]})</div>
        </div>
        """, unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">GOAL</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="card">
            <div class="city-name">🔴 {goal_city["name"]}</div>
            <div class="city-country">{goal_city["country"]} ({goal_city["country_code"]})</div>
        </div>
        """, unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">WHERE TO NEXT?</div>', unsafe_allow_html=True)
    st.caption(f"最大 {max_distance:.0f} km 以内の都市へ移動できます。")
    next_query = st.text_input("次の都市", placeholder="例：Kyoto / kyoto / 京都", label_visibility="collapsed", key="next_city_input")

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

                if st.button("🚶  MOVE", use_container_width=True, type="primary", key="exact_move"):
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
                st.info("同名の都市があります。移動先を選択してください。")
                labels = [f"{city_display_name(item['city'])} — {item['distance']:.1f} km" for item in exact_candidates]
                selected_index = st.selectbox("移動先", range(len(exact_candidates)), format_func=lambda i: labels[i], key="exact_city_selection")
                selected_city = exact_candidates[selected_index]["city"]

                if st.button("🚶  MOVE", use_container_width=True, type="primary", key="exact_multiple_move"):
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
                    if st.button("🚶  MOVE", use_container_width=True, type="primary", key="fuzzy_move"):
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
    st.markdown('<div class="section-label">LIVE MAP</div>', unsafe_allow_html=True)
    game_map = create_map(visited_cities, start_city, goal_city, current_city)
    st_folium(game_map, width=None, height=650, returned_objects=[])

st.divider()

route_col, stats_col = st.columns([1.7, 1], gap="large")

with route_col:
    st.markdown('<div class="section-label">ROUTE</div>', unsafe_allow_html=True)
    if len(visited_cities) == 1:
        st.caption("STARTからゲームが始まりました。次の都市を入力してください。")
    else:
        for i, city in enumerate(visited_cities):
            if i == 0:
                st.markdown(f"🟢 **{city['name']}**")
            else:
                previous = visited_cities[i - 1]
                distance = calculate_distance(previous, city)
                st.caption(f"↓ {distance:.1f} km")
                icon = "🟠" if i == len(visited_cities) - 1 else "📍"
                st.markdown(f"{icon} **{city['name']}**")

with stats_col:
    st.markdown('<div class="section-label">GAME INFO</div>', unsafe_allow_html=True)
    s1, s2 = st.columns(2)
    s1.metric("VISITED", len(visited_cities))
    s2.metric("TO GOAL", f"{current_distance_to_goal:.1f} km")
    st.metric("TOTAL DISTANCE", f"{total_distance:.1f} km")

st.divider()
if st.button("🔄 RESET GAME"):
    reset_game()
    st.rerun()