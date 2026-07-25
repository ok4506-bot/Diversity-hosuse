# -*- coding: utf-8 -*-
"""
격자 단위 주거건축물 다양성(Shannon Index) 결과를 행정동 단위로 집계하여
Streamlit 웹지도용 경량 GeoJSON으로 변환하는 전처리 스크립트.

** 로컬 Spyder에서 1회만 실행 ** (Streamlit 앱 자체에는 geopandas를 쓰지 않음 -
   Streamlit Cloud에서 GDAL/geopandas 설치가 까다롭고 자주 실패하기 때문)

출력물: seoul_dong_diversity.geojson  -> 이 파일을 app.py와 함께 GitHub repo에 올리면 됨
"""

import geopandas as gpd
import pandas as pd

# =========================================================
# 0. 경로 설정
# =========================================================
GRID_RESULT_GPKG = r"seoul_housing_diversity_grid.gpkg"   # 이전 단계 결과물
DONG_SHP = r"bnd_dong_11_2024_2Q.shp"                       # 행정동 경계 (SGIS에서 다운로드), 경로 수정 필요
OUT_GEOJSON = r"seoul_dong_diversity.geojson"

# =========================================================
# 1. 데이터 로드
# =========================================================
grid = gpd.read_file(GRID_RESULT_GPKG)      # EPSG:5179, columns: GRID_CD, shannon, n_bldg, n_type
dong = gpd.read_file(DONG_SHP)              # 행정동 경계

print("=== 격자 결과 ===")
print(grid.crs, grid.shape)
print(grid.columns.tolist())

print("\n=== 행정동 경계 ===")
print(dong.crs, dong.shape)
print(dong.columns.tolist())
print(dong.head(3))

# ↑ 이 출력 보고 행정동명/행정동코드 컬럼명이 ADM_NM, ADM_CD가 맞는지 확인!
#   다르면 아래 DONG_NAME_COL, DONG_CODE_COL 값을 실제 컬럼명으로 바꿔주세요.
DONG_NAME_COL = "ADM_NM"
DONG_CODE_COL = "ADM_CD"

# =========================================================
# 2. 좌표계 통일
# =========================================================
if grid.crs != dong.crs:
    dong = dong.to_crs(grid.crs)

# =========================================================
# 3. 격자 중심점 - 행정동 공간조인
# =========================================================
grid_pt = grid.copy()
grid_pt['geometry'] = grid_pt.geometry.centroid

joined = gpd.sjoin(
    grid_pt[['GRID_CD', 'shannon', 'n_bldg', 'n_type', 'geometry']],
    dong[[DONG_NAME_COL, DONG_CODE_COL, 'geometry']],
    how='inner', predicate='within'
)
print(f"\n격자->행정동 매칭 수: {len(joined)} / 전체 격자 {len(grid)}")

# 건물이 하나도 없는 격자(shannon=0, n_bldg=0)는 다양성 집계에서 제외
joined_valid = joined[joined['n_bldg'] > 0].copy()

# =========================================================
# 4. 행정동별 집계
# =========================================================
# 다양성 지수는 건물 수로 가중평균 (건물 10채 격자와 1채 격자를 동일하게 반영하면 왜곡되므로)
def weighted_mean(df, val_col, weight_col):
    w = df[weight_col]
    return (df[val_col] * w).sum() / w.sum() if w.sum() > 0 else 0

agg_rows = []
for code, g in joined_valid.groupby(DONG_CODE_COL):
    name = g[DONG_NAME_COL].iloc[0]
    agg_rows.append({
        DONG_CODE_COL: code,
        DONG_NAME_COL: name,
        'shannon_mean': weighted_mean(g, 'shannon', 'n_bldg'),   # 건물수 가중평균 다양성
        'n_bldg_sum': int(g['n_bldg'].sum()),                     # 행정동 내 총 주거건물 수
        'n_grid': g['GRID_CD'].nunique()                          # 집계에 쓰인 격자 수
    })

dong_stat = pd.DataFrame(agg_rows)
print("\n=== 행정동별 집계 결과 (상위 10개) ===")
print(dong_stat.sort_values('shannon_mean', ascending=False).head(10))

# =========================================================
# 5. 지오메트리 결합 + 웹지도용 좌표계(WGS84)로 변환 + 경량화
# =========================================================
dong_result = dong[[DONG_CODE_COL, DONG_NAME_COL, 'geometry']].merge(
    dong_stat.drop(columns=[DONG_NAME_COL]), on=DONG_CODE_COL, how='left'
)

# 다양성 데이터 없는 행정동(주거건물이 거의 없는 상업/공업 지역 등)은 0 처리
dong_result[['shannon_mean', 'n_bldg_sum', 'n_grid']] = (
    dong_result[['shannon_mean', 'n_bldg_sum', 'n_grid']].fillna(0)
)

# 웹지도(folium/leaflet/plotly)는 WGS84(EPSG:4326) 위경도 좌표를 씀
dong_result = dong_result.to_crs(epsg=4326)

# GitHub/Streamlit Cloud에 올릴 거라 파일 용량을 줄여야 함 -> 경계선 단순화
# tolerance 단위는 degree (대략 0.0005 ~= 50m 수준 단순화, 필요시 조정)
dong_result['geometry'] = dong_result.geometry.simplify(0.0005, preserve_topology=True)

# =========================================================
# 6. GeoJSON 저장
# =========================================================
dong_result.to_file(OUT_GEOJSON, driver='GeoJSON')
print(f"\n저장 완료: {OUT_GEOJSON}")
print(f"파일 크기 확인 후 (수 MB 넘으면) simplify tolerance를 더 키우는 걸 권장")
