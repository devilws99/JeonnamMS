import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# ----------------------------------------
# 1. 페이지 기본 설정
# ----------------------------------------
st.set_page_config(layout="wide", page_title="전국 시군구 고령화 지도")
st.title("🗺️ 전국 시군구 고령화율 및 경제 지표 지도")
st.markdown("시군구별 고령화율을 확인하고, **지도에서 지역을 클릭**하여 해당 시도의 1인당 경제 지표를 확인해 보세요.")

# ----------------------------------------
# 2. 데이터 불러오기 및 전처리 (캐싱 적용)
# ----------------------------------------
@st.cache_data
def load_data():
    # 2-1. 인구 데이터 불러오기
    url_pop = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(url_pop, dtype={'코드': str})
    
    # 가장 최신 연도 필터링
    latest_year = df['연도'].max()
    df = df[df['연도'] == latest_year]
    
    # 읍면동 단위 '코드'(10자리) 앞 5자리를 잘라 '시군구코드' 생성
    df['시군구코드'] = df['코드'].str[:5]
    
    # 65세 이상인 열 추출
    total_cols = [col for col in df.columns if col.startswith('계_')]
    def is_old_age(col_name):
        num_str = col_name.replace('계_', '').replace('세 이상', '').replace('세', '')
        try:
            return int(num_str) >= 65
        except ValueError:
            return False
            
    old_cols = [col for col in total_cols if is_old_age(col)]
    
    # 시군구 단위 인구수 합산
    grouped = df.groupby(['시군구코드', '시도', '시군구'])[total_cols].sum().reset_index()
    grouped['총인구'] = grouped[total_cols].sum(axis=1)
    grouped['고령인구'] = grouped[old_cols].sum(axis=1)
    
    # 고령화율(%) 및 5단계 비율 구간 계산
    grouped['고령화율'] = (grouped['고령인구'] / grouped['총인구']) * 100
    bins = [-1, 19, 23, 28, 38, 101] 
    labels = ['19% 미만', '19%~23%', '23%~28%', '28%~38%', '38% 이상']
    grouped['비율 구간'] = pd.cut(grouped['고령화율'], bins=bins, labels=labels, right=False)
    
    return grouped, latest_year, labels

@st.cache_data
def load_geojson():
    # 2-2. 지도 경계 GeoJSON 데이터 불러오기
    url_geo = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(url_geo)
    return response.json()

@st.cache_data
def load_kosis_eco_data():
    # 2-3. 제공된 이미지(KOSIS) 기준 시도별 경제 지표 데이터 내장 (2022년 p, 단위: 천원)
    data = {
        '시도_정규화': ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'],
        '1인당 지역내총생산': [51612, 31611, 26736, 35295, 30900, 33682, 77511, 37875, 39969, 34426, 48616, 58937, 32464, 51422, 43886, 36501, 31150],
        '1인당 지역총소득': [57236, 32293, 31056, 37442, 34844, 35848, 60971, 41372, 43635, 33198, 40673, 48015, 34299, 34098, 38391, 35540, 33525],
        '1인당 개인소득': [26112, 22577, 22368, 22406, 23669, 24220, 26066, 23215, 23136, 22395, 22533, 22481, 22262, 22298, 21981, 21887, 21508],
        '1인당 민간소비': [24455, 20637, 19903, 18706, 20361, 21065, 21097, 18571, 19307, 18457, 17536, 17878, 17614, 17919, 17841, 18766, 19125]
    }
    return pd.DataFrame(data)

# 시도 이름을 두 글자(정규화)로 통일하는 함수 (데이터 매칭용)
def normalize_sido(sido_name):
    if '서울' in sido_name: return '서울'
    if '부산' in sido_name: return '부산'
    if '대구' in sido_name: return '대구'
    if '인천' in sido_name: return '인천'
    if '광주' in sido_name: return '광주'
    if '대전' in sido_name: return '대전'
    if '울산' in sido_name: return '울산'
    if '세종' in sido_name: return '세종'
    if '경기' in sido_name: return '경기'
    if '강원' in sido_name: return '강원'
    if '충북' in sido_name or '충청북도' in sido_name: return '충북'
    if '충남' in sido_name or '충청남도' in sido_name: return '충남'
    if '전북' in sido_name or '전라북도' in sido_name: return '전북'
    if '전남' in sido_name or '전라남도' in sido_name: return '전남'
    if '경북' in sido_name or '경상북도' in sido_name: return '경북'
    if '경남' in sido_name or '경상남도' in sido_name: return '경남'
    if '제주' in sido_name: return '제주'
    return sido_name

# 데이터 로딩
grouped_df, data_year, category_labels = load_data()
geojson_data = load_geojson()
df_eco = load_kosis_eco_data()

st.caption(f"인구 데이터 기준 연도: {data_year}년 / 경제 지표 기준 연도: 2022년 (단위: 천원)")

# ----------------------------------------
# 3. 지도 그리기 (Plotly Express)
# ----------------------------------------
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
    locations='시군구코드',
    featureidkey='properties.코드',
    color='비율 구간',
    color_discrete_map=color_discrete_map,
    category_orders={'비율 구간': category_labels},
    hover_name='시군구',
    hover_data={
        '시군구코드': False, 
        '시도': True,
        '비율 구간': False, 
        '고령화율': ':.1f'
    }
)

fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    margin={"r":0,"t":0,"l":0,"b":0},
    legend_title_text='고령화율 구간'
)

# ----------------------------------------
# 4. 지도 클릭 이벤트 연동 (on_select)
# ----------------------------------------
# 사용자가 지도에서 지역을 클릭하면 이벤트를 받아옵니다.
selected_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

st.markdown("### 💰 선택한 지역의 경제 지표 (해당 시도 기준)")

# 선택(클릭)된 데이터가 있는지 확인
if selected_data and "selection" in selected_data and selected_data["selection"]["points"]:
    # 딕셔너리에서 클릭한 지역의 코드 추출
    clicked_code = selected_data["selection"]["points"][0]["location"]
    
    # 코드를 바탕으로 그룹 데이터에서 해당 시도 찾기
    sido_name = grouped_df[grouped_df['시군구코드'] == clicked_code]['시도'].values[0]
    sigungu_name = grouped_df[grouped_df['시군구코드'] == clicked_code]['시군구'].values[0]
    
    st.info(f"선택 지역: **{sido_name} {sigungu_name}**")
    
    # 정규화된 시도 이름으로 경제 데이터 매칭
    norm_sido = normalize_sido(sido_name)
    eco_row = df_eco[df_eco['시도_정규화'] == norm_sido]
    
    if not eco_row.empty:
        # 민간소비까지 포함하여 4개의 컬럼으로 구성
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("1인당 지역내총생산", f"{eco_row['1인당 지역내총생산'].values[0]:,} 천원")
        col2.metric("1인당 지역총소득", f"{eco_row['1인당 지역총소득'].values[0]:,} 천원")
        col3.metric("1인당 개인소득", f"{eco_row['1인당 개인소득'].values[0]:,} 천원")
        col4.metric("1인당 민간소비", f"{eco_row['1인당 민간소비'].values[0]:,} 천원")
else:
    # 아무것도 클릭하지 않았을 때의 안내 문구
    st.info("👆 지도에서 원하는 시군구를 클릭해보세요. 해당 시도의 경제 지표가 이곳에 나타납니다.")

# ----------------------------------------
# 5. 상위/하위 10곳 표 그리기
# ----------------------------------------
st.divider()
st.subheader("📊 한눈에 보는 고령화율 상위/하위 10곳")

col_t1, col_t2 = st.columns(2)

def prep_table(df, sort_asc=False):
    sorted_df = df.sort_values(by='고령화율', ascending=sort_asc).head(10)
    sorted_df = sorted_df[['시도', '시군구', '고령화율']].reset_index(drop=True)
    sorted_df.index = sorted_df.index + 1  
    return sorted_df

top_10 = prep_table(grouped_df, sort_asc=False)
bottom_10 = prep_table(grouped_df, sort_asc=True)

with col_t1:
    st.markdown("**🔴 고령화율 가장 높은 곳 (Top 10)**")
    st.dataframe(
        top_10,
        use_container_width=True,
        column_config={"고령화율": st.column_config.NumberColumn(format="%.1f%%")}
    )

with col_t2:
    st.markdown("**🔵 고령화율 가장 낮은 곳 (Top 10)**")
    st.dataframe(
        bottom_10,
        use_container_width=True,
        column_config={"고령화율": st.column_config.NumberColumn(format="%.1f%%")}
    )
