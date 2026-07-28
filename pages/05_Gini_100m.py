# -*- coding: utf-8 -*-
"""
100m(또는 확대) 격자 근린생활시설 다양성(지니계수) 뷰어 - Streamlit

* 무거운 연산(SHP 로딩, 공간조인, dissolve)은 로컬 PC에서
  grid_gini_analysis.py 로 미리 끝내고, 여기서는 그 결과물만 업로드해서
  가볍게 지도로 확인합니다.
* geopandas/GDAL 등 무거운 지리공간 라이브러리가 필요 없어 배포가 훨씬 간단합니다.

필요한 파일 (grid_gini_analysis.py 실행 결과물):
    1) grid_gini_{셀크기}m.geojson   - 필수. 셀별 gini 등 속성이 담긴 폴리곤
    2) poi_with_grid_id.csv          - 선택. 있으면 셀별 로렌츠 곡선/업종 구성까지 확인 가능

실행 방법:
    streamlit run streamlit_grid_gini_viewer.py

필요 패키지 (가벼움):
    pip install streamlit streamlit-folium folium branca pandas numpy matplotlib
"""

import json

import numpy as np
import pandas as pd
import streamlit as st
import folium
import branca.colormap as cm
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ==============================
# 0. 기본 설정
# ==============================
st.set_page_config(page_title="격자 기반 근린 다양성 뷰어", layout="wide")


def set_korean_font():
    candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


set_korean_font()


# ==============================
# 1. 지니계수 / 로렌츠 곡선 함수 (셀별 상세보기에서 재사용)
# ==============================
def gini_coefficient(counts):
    x = np.asarray(counts, dtype=float)
    x = x[x >= 0]
    n = len(x)
    total = x.sum()
    if n == 0 or total == 0:
        return None, None
    x_sorted = np.sort(x)
    ranks = np.arange(1, n + 1)
    g = (2 * np.sum(ranks * x_sorted)) / (n * total) - (n + 1) / n
    g_max = (n - 1) / n
    return g, g_max


def lorenz_points(counts):
    x = np.sort(np.asarray(counts, dtype=float))
    total = x.sum()
    n = len(x)
    cum_pop = np.insert(np.arange(1, n + 1) / n, 0, 0)
    cum_val = np.insert(np.cumsum(x) / total, 0, 0) if total > 0 else np.zeros(n + 1)
    return cum_pop, cum_val


def geojson_center(geojson):
    """geopandas 없이 geojson 폴리곤들의 대략적인 중심 좌표(위경도 평균) 계산"""
    lons, lats = [], []

    def walk(coords):
        # 좌표가 [lon,lat] 쌍인지, 더 깊은 리스트인지 재귀적으로 판단
        if len(coords) >= 2 and isinstance(coords[0], (int, float)):
            lons.append(coords[0])
            lats.append(coords[1])
        else:
            for c in coords:
                walk(c)

    for feat in geojson["features"][:200]:  # 샘플링 (전체 순회는 느릴 수 있어 일부만)
        walk(feat["geometry"]["coordinates"])

    if lons:
        return sum(lats) / len(lats), sum(lons) / len(lons)
    return 37.5665, 126.9780  # 실패 시 서울시청 기본값


# ==============================
# 2. 사이드바 - 파일 업로드
# ==============================
st.sidebar.header("① 결과 파일 업로드")
geojson_file = st.sidebar.file_uploader(
    "grid_gini_*.geojson (필수)", type=["geojson", "json"]
)
poi_grid_file = st.sidebar.file_uploader(
    "poi_with_grid_id.csv (선택, 있으면 셀별 상세 로렌츠 곡선 확인 가능)", type=["csv"]
)

if geojson_file is None:
    st.title("근린생활시설 다양성(지니계수) 격자 뷰어")
    st.info("왼쪽 사이드바에서 `grid_gini_*.geojson` 파일을 업로드해주세요.")
    st.markdown(
        "- 이 파일은 로컬 PC에서 `grid_gini_analysis.py`를 실행하면 생성됩니다.\n"
        "- 함께 만들어지는 `poi_with_grid_id.csv`도 올리면, 특정 셀을 선택해서 "
        "업종 구성 로렌츠 곡선까지 확인할 수 있어요."
    )
    st.stop()

geojson = json.load(geojson_file)
if not geojson.get("features"):
    st.error("GeoJSON에 features가 없습니다.")
    st.stop()

props_sample = geojson["features"][0]["properties"]
if "gini" not in props_sample:
    st.error(f"GeoJSON 속성에 'gini'가 없습니다. 현재 속성: {list(props_sample.keys())}")
    st.stop()

id_field = "agg_id" if "agg_id" in props_sample else list(props_sample.keys())[0]

# ==============================
# 3. 결과 테이블 재구성 (지도/랭킹/다운로드용)
# ==============================
records = [feat["properties"] for feat in geojson["features"]]
result = pd.DataFrame(records)
if id_field != "agg_id":
    result = result.rename(columns={id_field: "agg_id"})

# ==============================
# 4. poi_with_grid_id.csv (선택) -> 셀별 업종 구성 pivot
# ==============================
pivot = None
if poi_grid_file is not None:
    poi_grid_df = pd.read_csv(poi_grid_file, encoding="utf-8-sig")
    gcol = "grid_id" if "grid_id" in poi_grid_df.columns else (
        "agg_id" if "agg_id" in poi_grid_df.columns else None
    )
    if gcol and "poi_type" in poi_grid_df.columns:
        pivot = poi_grid_df.pivot_table(index=gcol, columns="poi_type",
                                        aggfunc="size", fill_value=0)
    else:
        st.sidebar.warning("poi_with_grid_id.csv에 'grid_id'(또는 'agg_id')와 "
                            "'poi_type' 컬럼이 필요합니다. 셀별 상세보기는 생략됩니다.")

# ==============================
# 5. 지도 시각화
# ==============================
st.title("근린생활시설 다양성(지니계수) 격자 지도")
st.caption("지니계수가 낮을수록(초록) 업종이 고르게 분포 / 높을수록(빨강) 특정 업종에 편중됨. "
           "업종 n개 조사 시 이론상 최댓값은 1이 아니라 (n-1)/n 이므로, 셀 간 비교에는 "
           "정규화 값(gini_normalized)을 함께 참고하세요.")

vmin, vmax = result["gini"].min(), result["gini"].max()
colormap = cm.LinearColormap(
    ["#2ca25f", "#fee08b", "#d73027"], vmin=vmin, vmax=vmax,
    caption="지니계수 (업종 편중도, 초록=균형 · 빨강=편중)"
)

center_lat, center_lon = geojson_center(geojson)
m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")

tooltip_fields = [f for f in [id_field, "gini", "total_facilities", "n_types_present"]
                  if f in props_sample]
tooltip_aliases = {id_field: "격자ID", "gini": "지니계수",
                   "total_facilities": "총 시설수", "n_types_present": "존재 업종수"}

folium.GeoJson(
    geojson,
    style_function=lambda f: {
        "fillColor": colormap(f["properties"]["gini"]) if f["properties"].get("gini") is not None else "#cccccc",
        "color": "white", "weight": 0.3, "fillOpacity": 0.8,
    },
    highlight_function=lambda f: {"weight": 2, "color": "black"},
    tooltip=folium.GeoJsonTooltip(
        fields=tooltip_fields,
        aliases=[tooltip_aliases[f] for f in tooltip_fields],
    ),
).add_to(m)
colormap.add_to(m)

st_folium(m, width=1100, height=650)

# ==============================
# 6. 순위 테이블 + 다운로드
# ==============================
st.subheader("셀별 업종 편중도 순위")
show_cols = [c for c in ["agg_id", "gini", "gini_normalized", "total_facilities", "n_types_present"]
             if c in result.columns]

col1, col2 = st.columns(2)
with col1:
    st.markdown("**🔴 가장 편중된 셀 TOP 10**")
    st.dataframe(result.sort_values("gini", ascending=False)[show_cols].head(10)
                 .reset_index(drop=True), use_container_width=True)
with col2:
    st.markdown("**🟢 가장 균형잡힌 셀 TOP 10**")
    st.dataframe(result.sort_values("gini")[show_cols].head(10)
                 .reset_index(drop=True), use_container_width=True)

csv_bytes = result[show_cols].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button("📥 셀별 지니계수 결과 CSV 다운로드", csv_bytes,
                    file_name="grid_gini_result.csv", mime="text/csv")

# ==============================
# 7. 개별 셀 상세 (로렌츠 곡선) - poi_with_grid_id.csv 업로드 시에만 표시
# ==============================
if pivot is not None:
    st.subheader("셀별 상세 보기 (업종 구성 로렌츠 곡선)")
    pivot_index_str = pivot.index.astype(str)
    valid_ids = sorted(set(result["agg_id"].astype(str)) & set(pivot_index_str))

    if valid_ids:
        cell_choice = st.selectbox("격자 셀 선택", valid_ids)
        match_idx = pivot.index[pivot_index_str == cell_choice][0]
        row = pivot.loc[match_idx]
        counts = row.values.astype(float)
        g_sel, g_max_sel = gini_coefficient(counts)

        c1, c2 = st.columns(2)
        with c1:
            cum_pop, cum_val = lorenz_points(counts)
            fig, ax = plt.subplots(figsize=(5, 5))
            ax.plot([0, 1], [0, 1], "--", color="gray", label="완전균등선")
            ax.plot(cum_pop, cum_val, marker="o", color="steelblue", label="로렌츠 곡선")
            ax.fill_between(cum_pop, cum_pop, cum_val, color="steelblue", alpha=0.15)
            ax.set_xlabel("업종 누적 비율")
            ax.set_ylabel("시설수 누적 비율")
            ax.set_title(f"{cell_choice}\nGini={g_sel:.3f} (최댓값 {g_max_sel:.3f})")
            ax.legend(loc="upper left")
            st.pyplot(fig)
        with c2:
            st.markdown(f"**{cell_choice} 업종별 시설 수**")
            st.bar_chart(row.sort_values(ascending=False))
            st.metric("총 시설 수", int(counts.sum()))
            st.metric("존재하는 업종 수", int((counts > 0).sum()))
    else:
        st.caption("geojson과 poi_with_grid_id.csv의 격자ID가 일치하지 않습니다. "
                    "같은 grid_gini_analysis.py 실행 결과물 세트를 함께 올려주세요.")
else:
    st.caption("💡 셀별 로렌츠 곡선까지 보려면 'poi_with_grid_id.csv'도 함께 업로드해주세요.")
