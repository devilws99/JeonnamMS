import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# ----------------------------------------
# 1. 페이지 기본 설정
# ----------------------------------------
st.set_page_config(layout="wide", page_title="전국 시군구 고령화 지도")
st.title("🗺️ 전국 시군구 고령화율 지도")
st.markdown("시군구별 65세 이상 인구 비율을 5단계로 나누어 보여줍니다.")

# ----------------------------------------
# 2. 데이터 불러오기 및 전처리 (캐싱 적용)
# ----------------------------------------
@st.cache_data
def load_data():
    # 2-1. 인구 데이터 불러오기 (코드는 0이 사라지지 않도록 반드시 문자열로 읽음)
    url_pop = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(url_pop, dtype={'코드': str})
    
    # 가장 최신 연도 필터링
    latest_year = df['연도'].max()
    df = df[df['연도'] == latest_year]
    
    # 읍면동 단위의 '코드'(10자리) 앞 5자리를 잘라 '시군구코드' 생성
    df['시군구코드'] = df['코드'].str[:5]
    
    # 나이별 열 이름 중 '계_'로 시작하는 남녀 합산 데이터 열만 추출
    total_cols = [col for col in df.columns if col.startswith('계_')]
    
    # 65세 이상인 열만 판별하여 추출하는 함수
    def is_old_age(col_name):
        # '계_65세', '계_100세 이상' 등의 글자에서 숫자만 추출
        num_str = col_name.replace('계_', '').replace('세 이상', '').replace('세', '')
        try:
            return int(num_str) >= 65
        except ValueError:
            return False
            
    old_cols = [col for col in total_cols if is_old_age(col)]
    
    # 시군구 단위로 묶어서 인구수 합산
    # ('시도', '시군구' 이름도 그대로 가져오기 위해 그룹화에 포함)
    grouped = df.groupby(['시군구코드', '시도', '시군구'])[total_cols].sum().reset_index()
    
    # 총 인구 및 65세 이상 인구 계산
    grouped['총인구'] = grouped[total_cols].sum(axis=1)
    grouped['고령인구'] = grouped[old_cols].sum(axis=1)
    
    # 고령화율(%) 계산
    grouped['고령화율'] = (grouped['고령인구'] / grouped['총인구']) * 100
    
    # 2-2. 고령화율을 지정된 5단계 구간으로 나누기 (19, 23, 28, 38 기준)
    # right=False로 설정하여 [19~23 미만) 형태로 구간을 잡습니다.
    bins = [-1, 19, 23, 28, 38, 101] 
    labels = ['19% 미만', '19%~23%', '23%~28%', '28%~38%', '38% 이상']
    grouped['비율 구간'] = pd.cut(grouped['고령화율'], bins=bins, labels=labels, right=False)
    
    return grouped, latest_year, labels

@st.cache_data
def load_geojson():
    # 2-3. 지도 경계 GeoJSON 데이터 불러오기
    url_geo = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(url_geo)
    return response.json()

# 데이터 로딩 실행
grouped_df, data_year, category_labels = load_data()
geojson_data = load_geojson()

st.caption(f"데이터 기준 연도: {data_year}년")

# ----------------------------------------
# 3. 지도 그리기 (Plotly Express)
# ----------------------------------------
# 낮은 비율은 옅은 색, 높은 비율은 진한 색으로 색상(Hex) 직접 지정
color_discrete_map = {
    '19% 미만': '#fee5d9',
    '19%~23%': '#fcae91',
    '23%~28%': '#fb6a4a',
    '28%~38%': '#de2d26',
    '38% 이상': '#a50f15'
}

fig = px.choropleth(
    grouped_df,
    geojson=geojson_data,
    locations='시군구코드',           # 데이터프레임의 시군구코드
    featureidkey='properties.코드',    # GeoJSON의 5자리 코드 매칭
    color='비율 구간',                 # 단계구분도 색상 기준
    color_discrete_map=color_discrete_map,
    category_orders={'비율 구간': category_labels}, # 범례 순서 고정
    hover_name='시군구',
    hover_data={
        '시군구코드': False,          # 툴팁에서 코드는 숨김
        '시도': True,
        '비율 구간': False,           # 중복되므로 숨김
        '고령화율': ':.1f'            # 소수점 첫째 자리까지만 표시
    }
)

# 배경 지도 타일 없이 경계선만 보이도록 설정 (fitbounds로 한국 위치 자동 포커스)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    margin={"r":0,"t":0,"l":0,"b":0},
    legend_title_text='고령화율 구간'
)

# 스트림릿에 지도 출력
st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------
# 4. 상위/하위 10곳 표 그리기
# ----------------------------------------
st.divider()
st.subheader("📊 한눈에 보는 고령화율 상위/하위 10곳")

col1, col2 = st.columns(2)

# 순위를 1부터 예쁘게 보여주기 위한 전처리 함수
def prep_table(df, sort_asc=False):
    # 정렬 (sort_asc가 True면 오름차순(하위), False면 내림차순(상위))
    sorted_df = df.sort_values(by='고령화율', ascending=sort_asc).head(10)
    sorted_df = sorted_df[['시도', '시군구', '고령화율']].reset_index(drop=True)
    sorted_df.index = sorted_df.index + 1  # 인덱스(순위) 1부터 시작
    return sorted_df

top_10 = prep_table(grouped_df, sort_asc=False)
bottom_10 = prep_table(grouped_df, sort_asc=True)

with col1:
    st.markdown("**🔴 고령화율 가장 높은 곳 (Top 10)**")
    # column_config를 사용해 % 기호와 소수점 포맷팅
    st.dataframe(
        top_10,
        use_container_width=True,
        column_config={"고령화율": st.column_config.NumberColumn(format="%.1f%%")}
    )

with col2:
    st.markdown("**🔵 고령화율 가장 낮은 곳 (Top 10)**")
    st.dataframe(
        bottom_10,
        use_container_width=True,
        column_config={"고령화율": st.column_config.NumberColumn(format="%.1f%%")}
    )
