# -*- coding: utf-8 -*-
"""
서울시 주거 건축물 - 용적률(중밀도) 구간별 지리적 히트맵
Streamlit Cloud 배포용 - geopandas 없이 pandas + pydeck(deck.gl)만 사용

같은 repo 루트에 middle_density_points.csv 파일이 있어야 함
(전처리 스크립트 preprocess_middle_density_points.py로 로컬에서 미리 생성)
"""

import os
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="서울시 중밀도 주택 히트맵", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "middle_density_points.csv")


@st.cache_data
def load_points():
    return pd.read_csv(CSV_PATH)


df = load_points()

st.title("서울시 주거 건축물 밀도(용적률) 히트맵")
st.caption(
    f"주거 건축물 {len(df):,}건 (연면적·용적률 모두 기록된 건물만) | "
    "용적률 구간을 선택하면 그 구간에 속하는 건물의 공간적 밀집도를 히트맵으로 표시"
)

# =========================================================
# 사이드바
# =========================================================
st.sidebar.title("표시 옵션")

far_min, far_max = float(df["far"].min()), float(df["far"].max())
far_median = float(df["far"].median())

st.sidebar.markdown(f"용적률 중위값: **{far_median:.0f}%**")

far_range = st.sidebar.slider(
    "용적률(FAR) 구간 선택 (%)",
    min_value=0.0,
    max_value=min(far_max, 400.0),   # 극단값 제외하고 슬라이더 범위 제한
    value=(100.0, 200.0),            # 기본값: 중위값(약 154%)을 감싸는 중밀도 구간
    step=5.0,
)

opacity = st.sidebar.slider("히트맵 투명도", 0.1, 1.0, 0.8, step=0.05)
radius = st.sidebar.slider("히트맵 반경 (radius pixels)", 10, 100, 40, step=5)
intensity = st.sidebar.slider("히트맵 강도 (intensity)", 0.1, 3.0, 1.0, step=0.1)

filtered = df[(df["far"] >= far_range[0]) & (df["far"] <= far_range[1])]
st.sidebar.markdown(f"선택된 구간 건물 수: **{len(filtered):,}건** ({len(filtered)/len(df)*100:.1f}%)")

# =========================================================
# 지도 (pydeck HeatmapLayer)
# =========================================================
layer = pdk.Layer(
    "HeatmapLayer",
    data=filtered,
    get_position=["lon", "lat"],
    opacity=opacity,
    radius_pixels=radius,
    intensity=intensity,
    threshold=0.03,
)

view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10.2, pitch=0)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style="light",
)

st.pydeck_chart(deck, use_container_width=True, height=700)

st.caption(
    f"현재 선택 구간: 용적률 {far_range[0]:.0f}% ~ {far_range[1]:.0f}% | "
    "데이터 출처: 브이월드 GIS건물통합정보(AL_D010)"
)

# =========================================================
# 참고: 구간별 유형 구성
# =========================================================
if len(filtered) > 0:
    st.subheader("선택 구간 내 주거 유형 구성")
    type_counts = filtered["housing_type"].value_counts()
    st.bar_chart(type_counts)
