# -*- coding: utf-8 -*-
"""
서울시 행정동별 주거건축물 유형 다양성(Shannon Index) 지도
Streamlit Cloud 배포용

같은 repo 폴더에 seoul_dong_diversity.geojson 파일이 있어야 함
(전처리 스크립트 preprocess_dong_diversity.py로 로컬에서 미리 생성)
"""

import json
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="서울시 주거건축물 다양성 지도", layout="wide")

DONG_NAME_COL = "adm_nm"
DONG_CODE_COL = "adm_cd2"
GEOJSON_PATH = "seoul_dong_diversity.geojson"

# =========================================================
# 데이터 로드 (캐싱으로 재실행 시 매번 새로 안 읽도록)
# =========================================================
@st.cache_data
def load_data():
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)

    rows = [feat["properties"] for feat in geojson["features"]]
    df = pd.DataFrame(rows)
    return geojson, df

geojson, df = load_data()

# =========================================================
# 사이드바
# =========================================================
st.sidebar.title("서울시 주거건축물 다양성")
st.sidebar.markdown(
    "행정동 단위로 집계한 **Shannon Diversity Index**입니다.\n\n"
    "단독주택 / 아파트 / 연립주택 / 다세대주택 4개 유형의 "
    "건물 수 비율로 계산했으며, 값이 클수록 여러 유형이 고르게 섞여 있다는 뜻입니다."
)

min_bldg = st.sidebar.slider(
    "최소 건물 수 필터 (표본이 너무 적은 동 제외)",
    min_value=0, max_value=int(df["n_bldg_sum"].max()),
    value=10, step=10
)

df_filtered = df[df["n_bldg_sum"] >= min_bldg].copy()

# =========================================================
# 메인 - 지도
# =========================================================
st.title("서울시 행정동별 주거건축물 유형 다양성 지도")

fig = px.choropleth_mapbox(
    df_filtered,
    geojson=geojson,
    locations=DONG_CODE_COL,
    featureidkey=f"properties.{DONG_CODE_COL}",
    color="shannon_mean",
    color_continuous_scale="Blues",
    range_color=(df["shannon_mean"].min(), df["shannon_mean"].max()),
    mapbox_style="carto-positron",
    zoom=10,
    center={"lat": 37.5665, "lon": 126.9780},
    opacity=0.75,
    hover_name=DONG_NAME_COL,
    hover_data={
        DONG_CODE_COL: False,
        "shannon_mean": ":.3f",
        "n_bldg_sum": True,
        "n_grid": True,
    },
    labels={
        "shannon_mean": "다양성 지수",
        "n_bldg_sum": "주거건물 수",
        "n_grid": "집계 격자 수",
    },
)
fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=700)

st.plotly_chart(fig, use_container_width=True)

# =========================================================
# 랭킹 테이블
# =========================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("다양성 지수 상위 10개 동")
    top10 = df_filtered.sort_values("shannon_mean", ascending=False).head(10)
    st.dataframe(
        top10[[DONG_NAME_COL, "shannon_mean", "n_bldg_sum"]]
        .rename(columns={DONG_NAME_COL: "행정동", "shannon_mean": "다양성 지수", "n_bldg_sum": "건물 수"})
        .reset_index(drop=True),
        use_container_width=True,
    )

with col2:
    st.subheader("다양성 지수 하위 10개 동")
    bottom10 = df_filtered.sort_values("shannon_mean", ascending=True).head(10)
    st.dataframe(
        bottom10[[DONG_NAME_COL, "shannon_mean", "n_bldg_sum"]]
        .rename(columns={DONG_NAME_COL: "행정동", "shannon_mean": "다양성 지수", "n_bldg_sum": "건물 수"})
        .reset_index(drop=True),
        use_container_width=True,
    )

st.caption(
    "데이터 출처: 브이월드 GIS건물통합정보(AL_D010), 통계청 100m 표준격자, SGIS 행정동 경계 | "
    "다양성 지수는 격자별 Shannon Index를 건물 수로 가중평균하여 행정동 단위로 집계함"
)
