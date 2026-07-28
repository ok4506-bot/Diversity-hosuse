# -*- coding: utf-8 -*-
"""
서울시 근린생활시설(POI) 업종 다양성 대시보드 (Streamlit)
- kakao_poi_mapping_seoul.py 로 만든 POI 데이터(csv)를 입력받아
  행정동/법정동 단위로 업종 편중도(지니계수)를 지도에 시각화
- 업종 필터, 순위 테이블, 개별 지역 로렌츠 곡선까지 인터랙티브로 제공

실행 방법:
    streamlit run streamlit_diversity_app.py

필요 패키지:
    pip install streamlit streamlit-folium folium branca pandas numpy matplotlib --break-system-packages
"""

import json
import os

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
st.set_page_config(page_title="서울시 근린 다양성 지도", layout="wide")

# 스크립트와 같은 폴더에 두면 자동으로 잡히는 기본 행정동 경계 파일
DEFAULT_DONG_BOUNDARY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "seoul_dong_boundary.geojson"
)


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
# 1. 지니계수 계산 함수
# ==============================
def gini_coefficient(counts):
    """
    이산형(업종별 개수) 데이터의 지니계수.
    반환: (gini, 이론상 최댓값(n-1)/n)
    """
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


# ==============================
# 2. 사이드바 - 데이터 입력
# ==============================
st.sidebar.header("① 데이터 입력")

poi_file = st.sidebar.file_uploader(
    "POI 데이터 CSV (seoul_poi_data.csv 등)", type=["csv"]
)

level = st.sidebar.radio("② 행정구역 단위", ["행정동", "법정동"], horizontal=True)

boundary_file = st.sidebar.file_uploader(
    f"{level} 경계 GeoJSON"
    + ("  (비워두면 기본 제공 서울시 행정동 경계 사용)" if level == "행정동" else " (필수 업로드)"),
    type=["geojson", "json"],
)

if poi_file is None:
    st.title("서울시 근린생활시설 다양성(지니계수) 대시보드")
    st.info("왼쪽 사이드바에서 POI 데이터 CSV를 업로드하면 분석이 시작됩니다.")
    st.markdown(
        "- 입력 CSV는 최소한 `poi_type`(업종명) 컬럼과, 행정동/법정동 이름 컬럼(`dong` 등)을 포함해야 합니다.\n"
        "- 서울시 전체 POI 수집 스크립트(`kakao_poi_mapping_seoul.py`)의 출력물(`seoul_poi_data.csv`)을 그대로 사용할 수 있습니다."
    )
    st.stop()

df = pd.read_csv(poi_file, encoding="utf-8-sig")

if "poi_type" not in df.columns:
    st.error("CSV에 'poi_type' 컬럼이 없습니다. 업종 구분 컬럼이 필요합니다.")
    st.stop()

# ==============================
# 3. 업종 필터
# ==============================
all_types = sorted(df["poi_type"].unique())
selected_types = st.sidebar.multiselect(
    "③ 분석에 포함할 업종", all_types, default=all_types
)
df = df[df["poi_type"].isin(selected_types)]

if df.empty:
    st.warning("선택된 업종에 해당하는 데이터가 없습니다.")
    st.stop()

# ==============================
# 4. 지역 구분 컬럼 결정
# ==============================
default_group_col = "dong" if "dong" in df.columns else df.columns[0]
group_col = st.sidebar.text_input(
    f"④ CSV 내 {level} 구분 컬럼명", value=default_group_col
)

if group_col not in df.columns:
    st.error(f"CSV에 '{group_col}' 컬럼이 없습니다. 실제 컬럼명을 정확히 입력해주세요. "
              f"(현재 컬럼: {list(df.columns)})")
    st.stop()

# 주의: 서울시에는 동일한 동 이름이 다른 구에 존재하는 경우가 있습니다
# (예: '신사동'은 강남구·관악구에 모두 존재). 동 이름만으로 그룹핑하면
# 서로 다른 지역이 하나로 합쳐지는 오류가 생기므로, gu 컬럼이 있으면
# '구+동' 조합을 내부 그룹핑 키로 사용합니다.
if "gu" in df.columns:
    df["_area_key"] = df["gu"].astype(str) + " " + df[group_col].astype(str)
    dup_names = df.drop_duplicates(subset=["_area_key"])[group_col].value_counts()
    dup_names = dup_names[dup_names > 1].index.tolist()
    if dup_names:
        st.sidebar.caption(f"⚠️ 동명이지역 감지: {', '.join(dup_names)} → 구+동 조합으로 구분 처리됨")
    internal_group_col = "_area_key"
else:
    internal_group_col = group_col

# ==============================
# 5. 경계 GeoJSON 로드
# ==============================
if boundary_file is not None:
    boundary = json.load(boundary_file)
elif level == "행정동" and os.path.exists(DEFAULT_DONG_BOUNDARY):
    with open(DEFAULT_DONG_BOUNDARY, encoding="utf-8") as f:
        boundary = json.load(f)
else:
    st.warning(f"{level} 경계 GeoJSON을 업로드해주세요. (법정동은 기본 제공 파일이 없습니다)")
    st.stop()

if not boundary.get("features"):
    st.error("경계 GeoJSON에 features가 없습니다.")
    st.stop()

prop_keys = list(boundary["features"][0]["properties"].keys())
default_name_field = "adm_nm" if "adm_nm" in prop_keys else prop_keys[0]
name_field = st.sidebar.selectbox(
    "⑤ 경계 파일의 지역명 속성(property)", prop_keys,
    index=prop_keys.index(default_name_field)
)

# ==============================
# 6. 지역별 업종 개수 집계 + 지니계수
#    (internal_group_col 기준으로 집계 -> 동명이지역 문제 방지)
# ==============================
pivot = df.pivot_table(index=internal_group_col, columns="poi_type", aggfunc="size", fill_value=0)

# 표시용 원래 이름 매핑 (내부키 -> 화면에 보여줄 동 이름)
display_name_map = df.drop_duplicates(subset=[internal_group_col]).set_index(internal_group_col)[group_col].to_dict()

records = []
for area_key, row in pivot.iterrows():
    vals = row.values.astype(float)
    if vals.sum() == 0:
        continue
    g, g_max = gini_coefficient(vals)
    records.append({
        internal_group_col: area_key,
        group_col: display_name_map.get(area_key, area_key),
        "gini": g,
        "gini_normalized": (g / g_max) if g_max else None,
        "total_facilities": int(vals.sum()),
        "n_types_present": int((vals > 0).sum()),
    })
gini_df = pd.DataFrame(records)

if gini_df.empty:
    st.warning("집계된 지역 데이터가 없습니다.")
    st.stop()

# ==============================
# 7. 경계 파일 매칭용 키 생성
#    (행정동 기본 파일의 adm_nm은 "서울특별시 OO구 OO동" 형식)
#    internal_group_col이 이미 "구 동" 조합(또는 gu 없으면 동 이름)이므로 그대로 활용
# ==============================
if "gu" in df.columns:
    gini_df["match_name"] = gini_df[internal_group_col].map(
        lambda s: f"서울특별시 {s}".strip()
    )
else:
    gini_df["match_name"] = gini_df[internal_group_col]

lookup = gini_df.set_index("match_name").to_dict("index")

matched, unmatched = 0, 0
for feat in boundary["features"]:
    nm = feat["properties"].get(name_field, "")
    info = lookup.get(nm)
    if info is None:
        # 완전일치 실패 시, 지역명이 접미어로 포함되는지 한번 더 시도 (예: 단순 동 이름만 일치)
        info = lookup.get(str(nm).split(" ")[-1]) if isinstance(nm, str) else None
    if info:
        feat["properties"]["_gini"] = round(info["gini"], 4)
        feat["properties"]["_gini_normalized"] = (
            round(info["gini_normalized"], 4) if info["gini_normalized"] is not None else None
        )
        feat["properties"]["_total_facilities"] = info["total_facilities"]
        feat["properties"]["_n_types_present"] = info["n_types_present"]
        matched += 1
    else:
        feat["properties"]["_gini"] = None
        feat["properties"]["_total_facilities"] = None
        feat["properties"]["_n_types_present"] = None
        unmatched += 1

st.sidebar.caption(f"✅ 경계-데이터 매칭: {matched}개 성공 / {unmatched}개 실패")
if unmatched > 0:
    st.sidebar.caption(
        "⚠️ 매칭 실패가 많다면 '경계 파일의 지역명 속성' 선택이나 "
        "CSV의 지역 구분 컬럼명을 다시 확인해주세요."
    )

# ==============================
# 8. 지도 시각화
# ==============================
st.title(f"서울시 {level}별 근린생활시설 다양성(지니계수) 지도")
st.caption("지니계수가 낮을수록(초록) 업종이 고르게 분포 / 높을수록(빨강) 특정 업종에 편중됨. "
           "업종 n개 조사 시 이론상 최댓값은 1이 아니라 (n-1)/n 이므로, 지역 간 비교에는 "
           "정규화 값(gini_normalized)을 함께 참고하세요.")

valid_gini = [f["properties"]["_gini"] for f in boundary["features"]
              if f["properties"]["_gini"] is not None]
vmin, vmax = (min(valid_gini), max(valid_gini)) if valid_gini else (0, 1)

colormap = cm.LinearColormap(
    ["#2ca25f", "#fee08b", "#d73027"], vmin=vmin, vmax=vmax,
    caption="지니계수 (업종 편중도, 초록=균형 · 빨강=편중)"
)


def style_function(feature):
    g = feature["properties"]["_gini"]
    if g is None:
        return {"fillColor": "#cccccc", "color": "white", "weight": 0.5, "fillOpacity": 0.35}
    return {"fillColor": colormap(g), "color": "white", "weight": 0.7, "fillOpacity": 0.78}


m = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles="CartoDB positron")

folium.GeoJson(
    boundary,
    style_function=style_function,
    highlight_function=lambda f: {"weight": 2.5, "color": "black"},
    tooltip=folium.GeoJsonTooltip(
        fields=[name_field, "_gini", "_total_facilities", "_n_types_present"],
        aliases=["지역", "지니계수", "총 시설수", "존재 업종수"],
        localize=True,
    ),
).add_to(m)
colormap.add_to(m)

st_folium(m, width=1100, height=650)

# ==============================
# 9. 순위 테이블
# ==============================
st.subheader(f"{level}별 업종 편중도 순위")
show_cols = ["gu", group_col, "gini", "gini_normalized", "total_facilities", "n_types_present"] \
    if "gu" in df.columns else [group_col, "gini", "gini_normalized", "total_facilities", "n_types_present"]
if "gu" in df.columns and "gu" not in gini_df.columns:
    gini_df["gu"] = gini_df[internal_group_col].str.rsplit(" ", n=1).str[0]

col1, col2 = st.columns(2)
with col1:
    st.markdown("**🔴 가장 편중된 지역 TOP 10** (특정 업종 쏠림)")
    st.dataframe(
        gini_df.sort_values("gini", ascending=False)[show_cols].head(10)
        .reset_index(drop=True),
        use_container_width=True,
    )
with col2:
    st.markdown("**🟢 가장 균형잡힌 지역 TOP 10** (업종 다양성 높음)")
    st.dataframe(
        gini_df.sort_values("gini")[show_cols].head(10).reset_index(drop=True),
        use_container_width=True,
    )

csv_bytes = gini_df[show_cols].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    f"📥 {level}별 지니계수 결과 CSV 다운로드", csv_bytes,
    file_name=f"gini_by_{group_col}.csv", mime="text/csv"
)

# ==============================
# 10. 개별 지역 상세 (로렌츠 곡선 + 업종 구성)
# ==============================
st.subheader("지역별 상세 보기")
# 화면에는 보기 좋은 이름(구+동)을 보여주되, 내부적으로는 유일 키로 조회
option_map = dict(zip(gini_df["match_name"].str.replace("서울특별시 ", "", regex=False),
                      gini_df[internal_group_col]))
display_choice = st.selectbox(f"{level} 선택", sorted(option_map.keys()))
area_choice = option_map[display_choice]

row = pivot.loc[area_choice]
counts = row.values.astype(float)
g_sel, g_max_sel = gini_coefficient(counts)

c1, c2 = st.columns([1, 1])

with c1:
    cum_pop, cum_val = lorenz_points(counts)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="완전균등선")
    ax.plot(cum_pop, cum_val, marker="o", color="steelblue", label="로렌츠 곡선")
    ax.fill_between(cum_pop, cum_pop, cum_val, color="steelblue", alpha=0.15)
    ax.set_xlabel("업종 누적 비율")
    ax.set_ylabel("시설수 누적 비율")
    ax.set_title(f"{display_choice}\nGini={g_sel:.3f} (최댓값 {g_max_sel:.3f})")
    ax.legend(loc="upper left")
    st.pyplot(fig)

with c2:
    st.markdown(f"**{display_choice} 업종별 시설 수**")
    st.bar_chart(row.sort_values(ascending=False))
    st.metric("총 시설 수", int(counts.sum()))
    st.metric("존재하는 업종 수", int((counts > 0).sum()))
