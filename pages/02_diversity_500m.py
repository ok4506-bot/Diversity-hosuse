# -*- coding: utf-8 -*-
"""
서울시 격자 단위 주거건축물 유형 다양성(Shannon Index) 지도 (100m/500m 전환 가능)
Streamlit Cloud 배포용 - geopandas 없이 pydeck(deck.gl)만 사용

같은 repo 루트에 seoul_grid_diversity2.geojson(100m), seoul_grid_diversity_500m.geojson(500m)
두 파일이 모두 있어야 함 (전처리 스크립트로 로컬에서 미리 생성)
"""

import json
import os
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="서울시 주거건축물 다양성 지도", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 격자 해상도별 geojson 파일 경로 (둘 다 repo 루트에 있어야 함)
GEOJSON_PATHS = {
    "100m": os.path.join(BASE_DIR, "..", "seoul_grid_diversity2.geojson"),
    "500m": os.path.join(BASE_DIR, "..", "seoul_grid_diversity_500m.geojson"),
}


@st.cache_data
def load_geojson(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


st.title("서울시 격자별 주거건축물 유형 다양성 지도")

# =========================================================
# 사이드바 - 격자 해상도 선택
# =========================================================
st.sidebar.title("표시 옵션")

resolution = st.sidebar.radio("격자 크기", ["100m", "500m"], horizontal=True)
geojson = load_geojson(GEOJSON_PATHS[resolution])

st.caption(
    f"[{resolution} 격자] 건물이 있는 격자 {len(geojson['features']):,}개 표시 중 | "
    "단독주택 / 아파트 / 연립주택 / 다세대주택 비율 기반 Shannon Diversity Index"
)

# =========================================================
# 사이드바 - 레이어 토글 (동시에 겹쳐서 표시 가능)
# =========================================================
show_shannon = st.sidebar.checkbox("다양성 지수 표시 (채우기 색)", value=True)
show_lisa = st.sidebar.checkbox("공간 클러스터 표시 (테두리 색, LISA)", value=False)

min_bldg = st.sidebar.slider("최소 건물 수 필터", 0, 50, 0, step=1)

st.sidebar.markdown("---")

if show_shannon:
    shannon_opacity = st.sidebar.slider("다양성 지수 투명도", 0.1, 1.0, 0.6, step=0.1)
if show_lisa:
    lisa_line_width = st.sidebar.slider("클러스터 테두리 두께", 1, 8, 3, step=1)

features = [
    f for f in geojson["features"]
    if f["properties"]["n_bldg"] >= min_bldg
]
filtered_geojson = {"type": "FeatureCollection", "features": features}

st.sidebar.markdown(f"현재 표시 중: **{len(features):,}개** 격자")

if show_shannon:
    st.sidebar.markdown(
        "**다양성 지수 범례**\n\n"
        "🔵 진한 파랑 = 다양성 높음 (여러 유형 혼재)\n\n"
        "⚪ 연한 파랑 = 다양성 낮음 (한 유형 위주)"
    )
if show_lisa:
    st.sidebar.markdown(
        "**LISA 클러스터 범례 (테두리)**\n\n"
        "🔴 High-High = 다양성 핫스팟\n\n"
        "🔵 Low-Low = 다양성 콜드스팟\n\n"
        "🟠🔵 High-Low / Low-High = 이상치\n\n"
        "⚪ 회색 = 통계적으로 유의하지 않음"
    )

# =========================================================
# 지도 (pydeck / deck.gl) - 두 레이어를 겹쳐서 표시
# =========================================================
layers = []

if show_shannon:
    layers.append(pdk.Layer(
        "GeoJsonLayer",
        filtered_geojson,
        id="shannon-layer",
        opacity=shannon_opacity,
        stroked=False,
        filled=True,
        get_fill_color="properties.shannon_color",
        pickable=True,
        auto_highlight=True,
    ))

if show_lisa:
    # 유의하지 않은(Not Significant) 격자는 테두리를 그리면 지도가 지저분해지므로 제외
    lisa_features = [
        f for f in filtered_geojson["features"]
        if f["properties"]["lisa_cluster"] != "Not Significant"
    ]
    lisa_geojson = {"type": "FeatureCollection", "features": lisa_features}

    layers.append(pdk.Layer(
        "GeoJsonLayer",
        lisa_geojson,
        id="lisa-layer",
        filled=False,
        stroked=True,
        get_line_color="properties.lisa_color",
        line_width_min_pixels=lisa_line_width,
        pickable=True,
        auto_highlight=True,
    ))

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
        "<b>클러스터:</b> {lisa_cluster} (p={lisa_p})<br/>"
        "<b>주거건물 수:</b> {n_bldg}<br/>"
        "<b>유형 수:</b> {n_type}"
    ),
    "style": {"backgroundColor": "steelblue", "color": "white"},
}

if layers:
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="light",
    )
    st.pydeck_chart(deck, use_container_width=True, height=700)
else:
    st.info("사이드바에서 표시할 레이어를 하나 이상 선택해주세요.")

st.caption(
    "데이터 출처: 브이월드 GIS건물통합정보(AL_D010), 통계청 표준격자(100m/500m) | "
    "다양성 지수 = 격자 내 단독주택/아파트/연립주택/다세대주택 건물 수 비율의 Shannon Entropy"
)
