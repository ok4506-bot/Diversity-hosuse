# -*- coding: utf-8 -*-
"""
서울시 100m 격자 단위 주거건축물 유형 다양성(Shannon Index) 지도
Streamlit Cloud 배포용 - geopandas 없이 pydeck(deck.gl)만 사용

같은 repo 폴더에 seoul_grid_diversity.geojson 파일이 있어야 함
(전처리 스크립트 preprocess_grid_for_web.py로 로컬에서 미리 생성)
"""

import json
import os
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="서울시 주거건축물 다양성 지도", layout="wide")

# 이 스크립트 파일이 있는 폴더를 기준으로 경로를 잡음
# (Streamlit 멀티페이지 앱은 실행 위치가 repo 루트/페이지 폴더로 뒤섞일 수 있어서
#  __file__ 기준 절대경로를 쓰는 게 안전함)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEOJSON_PATH = os.path.join(BASE_DIR, "..", "seoul_grid_diversity.geojson")


@st.cache_data
def load_geojson():
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


geojson = load_geojson()

st.title("서울시 100m 격자별 주거건축물 유형 다양성 지도")
st.caption(
    f"건물이 있는 격자 {len(geojson['features']):,}개 표시 중 | "
    "단독주택 / 아파트 / 연립주택 / 다세대주택 비율 기반 Shannon Diversity Index"
)

# =========================================================
# 사이드바 - 필터
# =========================================================
st.sidebar.title("표시 옵션")
min_bldg = st.sidebar.slider("최소 건물 수 필터", 0, 50, 0, step=1)
opacity = st.sidebar.slider("격자 투명도", 0.1, 1.0, 0.7, step=0.1)

features = [
    f for f in geojson["features"]
    if f["properties"]["n_bldg"] >= min_bldg
]
filtered_geojson = {"type": "FeatureCollection", "features": features}

st.sidebar.markdown(f"현재 표시 중: **{len(features):,}개** 격자")

# =========================================================
# 지도 (pydeck / deck.gl)
# =========================================================
layer = pdk.Layer(
    "GeoJsonLayer",
    filtered_geojson,
    opacity=opacity,
    stroked=True,
    filled=True,
    get_fill_color="properties.fill_color",
    get_line_color=[255, 255, 255, 60],
    line_width_min_pixels=0.5,
    pickable=True,
    auto_highlight=True,
)

view_state = pdk.ViewState(
    latitude=37.5665,
    longitude=126.9780,
    zoom=10.2,
    pitch=0,
)

tooltip = {
    "html": (
        "<b>격자 코드:</b> {GRID_CD}<br/>"
        "<b>다양성 지수:</b> {shannon}<br/>"
        "<b>주거건물 수:</b> {n_bldg}<br/>"
        "<b>유형 수:</b> {n_type}"
    ),
    "style": {"backgroundColor": "steelblue", "color": "white"},
}

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_style="light",
)

st.pydeck_chart(deck, use_container_width=True, height=700)

st.caption(
    "데이터 출처: 브이월드 GIS건물통합정보(AL_D010), 통계청 100m 표준격자 | "
    "다양성 지수 = 격자 내 단독주택/아파트/연립주택/다세대주택 건물 수 비율의 Shannon Entropy"
)
