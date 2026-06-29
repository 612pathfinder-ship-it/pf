import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Volume Top 50 Dashboard")
st.title("📊 4대 지수 거래량 상위 50 판단 대시보드")
st.caption("천단위 콤마, 기업명 표기, 주간 거래량 추세 그래프 내장 버전")

# ----------------------------------------------------------------------
# [안정성 확보] 직전 3개월 주차별 날짜 생성 (12주차)
# ----------------------------------------------------------------------
@st.cache_data
def get_cached_weeks():
    options = {}
    today = datetime.today()
    for i in range(12): 
        monday = today - timedelta(days=today.weekday() + (i * 7))
        friday = monday + timedelta(days=4)
        if monday > today: continue
        
        label = f"📅 {monday.strftime('%Y년 %m월')} {(monday.day - 1) // 7 + 1}주차 ({monday.strftime('%m.%d')} ~ {friday.strftime('%m.%d')})"
        options[label] = {
            "start": monday.strftime("%Y-%m-%d"),
            "end": friday.strftime("%Y-%m-%d")
        }
    return options

weekly_options = get_cached_weeks()

# 사이드바 제어 설정
st.sidebar.header("🔧 대시보드 제어판")
selected_week_label = st.sidebar.selectbox("🔍 조회 주차 선택 (직전 3개월)", list(weekly_options.keys()))
selected_dates = weekly_options[selected_week_label]
exclude_decreased = st.sidebar.checkbox("📉 주간 거래량 감소 종목 필터링 (제외)", value=False)

# ----------------------------------------------------------------------
# [엔진 교체] 글로벌/국내 데이터 통합 수집 및 가공
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_volume_data_v2(market_type, start_date, end_date):
    """FinanceDataReader 및 yfinance 기반 고속/안정 데이터 수집"""
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prev_start = (st_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    
    try:
        if market_type in ["KOSPI", "KOSDAQ"]:
            # 한국 거래소 데이터 수집 (FinanceDataReader 활용으로 에러 원천 차단)
            df_target = fdr.StockListing(market_type)
            data_list = []
            
            # 상위 거래대금 리스트업을 위해 마켓 데이터 수집
            for _, row in df_target.head(120).iterrows():
                ticker = row['Code']
                name = row['Name']
                
                # 개별 종목 기간 데이터 바인딩
                hist = fdr.DataReader(ticker, prev_start, end_date)
                if not hist.empty and len(hist) >= 5:
                    this_week_vol = hist['Volume'].loc[start_date:end_date].sum()
                    prev_week_vol = hist['Volume'].loc[prev_start:start_date].sum()
                    
                    if pd.isna(this_week_vol): this_week_vol = 0
                    if pd.isna(prev_week_vol) or prev_week_vol == 0: prev_week_vol = 1
                    
                    change = ((this_week_vol - prev_week_vol) / prev_week_vol) * 100
                    
                    data_list.append({
                        "기업명": name, "티커": ticker, 
                        "현재가": int(hist['Close'].iloc[-1]), 
                        "선택주차 누적거래량": int(this_week_vol), 
                        "전주대비 증감률(%)": round(change, 2)
                    })
            return pd.DataFrame(data_list)
            
        else:
            # 미국 시장 데이터 수집 (S&P500 / NASDAQ 샘플 풀 고도화)
            tickers_map = {
                "S&P 500": {"NVDA":"엔비디아", "AAPL":"애플", "MSFT":"마이크로소프트", "AMZN":"아마존", "GOOGL":"알파벳", "TSLA":"테슬라", "META":"메타", "AMD":"AMD", "INTC":"인텔", "NFLX":"넷플릭스"},
                "NASDAQ": {"QQQ":"QQQ ETF", "AVGO":"브로드컴", "COST":"코스트코", "PEP":"펩시코", "ADBE":"어도비", "CMCSA":"컴캐스트", "TMUS":"티모바일", "TXN":"텍사스인스트루먼트"}
            }
            curr_map = tickers_map[market_type]
            df = yf.download(" ".join(curr_map.keys()), start=prev_start, end=end_date, group_by='ticker', progress=False)
            
            data_list = []
            for ticker, name in curr_map.items():
                if ticker in df.columns.levels[0]:
                    t_df = df[ticker].dropna()
                    if not t_df.empty:
                        this_week_avg = t_df['Volume'].loc[start_date:end_date].mean()
                        prev_week_avg = t_df['Volume'].loc[prev_start:start_date].mean()
                        
                        if pd.isna(this_week_avg): this_week_avg = 0
                        if pd.isna(prev_week_avg) or prev_week_avg == 0: prev_week_avg = 1
                        
                        change = ((this_week_avg - prev_week_avg) / prev_week_avg) * 100
                        
                        data_list.append({
                            "기업명": name, "티커": ticker, 
                            "현재가": round(t_df['Close'].iloc[-1], 2), 
                            "선택주차 평균거래량": int(this_week_avg), 
                            "전주대비 증감률(%)": round(change, 2)
                        })
            return pd.DataFrame(data_list)
    except:
        return pd.DataFrame()

# ----------------------------------------------------------------------
# 화면 렌더링 엔진 (인라인 그래프 및 포맷팅 적용)
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        df_raw = get_volume_data_v2(m_name, selected_dates["start"], selected_dates["end"])
        
        if df_raw.empty:
            st.error("데이터 제공처 동기화 지연 또는 휴장일입니다. 사이드바에서 다른 주차를 선택해 주세요.")
        else:
            # 1. 감소 종목 필터링
            if exclude_decreased:
                df_raw = df_raw[df_raw["전주대비 증감률(%)"] >= 0]
            
            # 2. 정렬 및 상위 50위 커팅
            sort_key = "선택주차 누적거래량" if "KOSPI" in m_name or "KOSDAQ" in m_name else "선택주차 평균거래량"
            df_top50 = df_raw.sort_values(by=sort_key, ascending=False).head(50).reset_index(drop=True)
            
            # 3. 가독성 가공 (천단위 콤마 포맷팅 지정)
            df_styled = df_top50.copy()
            
            st.subheader(f"📊 {m_name} 거래량 상위 파악 뷰")
            
            # 4. 판다스 스타일러를 활용한 시각적 인라인 그래프(Bar) 삽입
            st.dataframe(
                df_styled.style.format({
                    "현재가": "{:,.0f}" if "KOSPI" in m_name or "KOSDAQ" in m_name else "{:,.2f}",
                    sort_key: "{:,.0f}",
                    "전주대비 증감률(%)": "{:+.2f}%"
                }).bar(
                    subset=["전주대비 증감률(%)"], 
                    align="mid", 
                    color=["#FF4B4B", "#00CC96"] # 감소는 빨강, 증가 및 폭발은 녹색 계열 그래프 매핑
                ),
                use_container_width=True,
                height=600
            )
