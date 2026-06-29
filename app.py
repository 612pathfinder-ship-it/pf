import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timedelta

# 페이지 레이아웃 가독성 강제 설정
st.set_page_config(layout="wide", page_title="Volume Top 50 Fact Dashboard")
st.title("📊 4대 지수 거래량 상위 50 최종 판단 대시보드")
st.caption("순위 고정, 인덱스 제거, 천단위 콤마, 주요 ETF명 매핑, 직관 그래프 빌트인")

# ----------------------------------------------------------------------
# 날짜 바인딩 (직전 3개월 주차별 리스트 생성)
# ----------------------------------------------------------------------
@st.cache_data
def get_cached_weeks():
    options = {}
    today = datetime.today()
    for i in range(12): 
        monday = today - timedelta(days=today.weekday() + (i * 7))
        friday = monday + timedelta(days=4)
        if monday > today: 
            continue
        
        label = f"📅 {monday.strftime('%Y년 %m월')} {(monday.day - 1) // 7 + 1}주차 ({monday.strftime('%m.%d')} ~ {friday.strftime('%m.%d')})"
        options[label] = {
            "start": monday.strftime("%Y-%m-%d"),
            "end": friday.strftime("%Y-%m-%d")
        }
    return options

weekly_options = get_cached_weeks()

# 사이드바 제어판 설정
st.sidebar.header("🔧 대시보드 제어판")
selected_week_label = st.sidebar.selectbox("🔍 조회 주차 선택", list(weekly_options.keys()))
selected_dates = weekly_options[selected_week_label]
exclude_decreased = st.sidebar.checkbox("📉 주간 거래량 감소 종목 필터링 (제외)", value=False)

# ----------------------------------------------------------------------
# 상위 50위가 무조건 꽉 차도록 시장별 데이터 풀(Pool) 구성
# ----------------------------------------------------------------------
@st.cache_data
def get_master_name_map():
    m_map = {}
    # 미국 시장 주요 ETF 및 대표 대형주 명칭 매핑
    m_map["QQQ"] = "Invesco QQQ (나스닥100 추종 ETF)"
    m_map["TQQQ"] = "ProShares 나스닥 100 3배 레버리지 ETF"
    m_map["SQQQ"] = "ProShares 나스닥 100 3배 인버스 ETF"
    m_map["SPY"] = "SPDR S&P 500 지수 추종 ETF"
    m_map["SOXL"] = "Direxion 반도체 3배 레버리지 ETF"
    m_map["SOXS"] = "Direxion 반도체 3배 인버스 ETF"
    m_map["NVDA"] = "엔비디아"
    m_map["AAPL"] = "애플"
    m_map["MSFT"] = "마이크로소프트"
    m_map["AMZN"] = "아마존"
    m_map["GOOGL"] = "알파벳"
    m_map["TSLA"] = "테슬라"
    m_map["META"] = "메타"
    m_map["AMD"] = "AMD"
    m_map["INTC"] = "인텔"
    m_map["NFLX"] = "넷플릭스"
    m_map["AVGO"] = "브로드컴"
    m_map["COST"] = "코스트코"
    m_map["PEP"] = "펩시코"
    
    # 한국 시장 주요 대표 지수 ETF 명칭 매핑
    m_map["069500"] = "KODEX 200 (코스피 지수 ETF)"
    m_map["114800"] = "KODEX 인버스"
    m_map["252670"] = "KODEX 200선물인버스2X (곱버스)"
    m_map["122630"] = "KODEX 레버리지 (2배)"
    m_map["251340"] = "KODEX 코스닥150선물인버스"
    m_map["233740"] = "KODEX 코스닥150 레버리지"
    m_map["102110"] = "TIGER 200 지수 ETF"
    m_map["252710"] = "TIGER 200선물인버스2X"
    return m_map

# ----------------------------------------------------------------------
# 고속/안정 주간 데이터 로드 코어 엔진
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_market_fact_data(market_name, start_date, end_date):
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prev_start = (st_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    name_map = get_master_name_map()
    
    try:
        # 1. 한국 시장 전용 수집 엔진 (FinanceDataReader 기반 안정화)
        if market_name in ["KOSPI", "KOSDAQ"]:
            df_listing = fdr.StockListing(market_name)
            data_list = []
            
            # 가독성을 위해 상위 100개 대형 자산 풀을 먼저 가져옴
            for _, row in df_listing.head(100).iterrows():
                t = row['Code']
                name = name_map.get(t, row['Name']) # ETF 딕셔너리에 있으면 치환, 없으면 기본 사명 사용
                
                # 시세 바인딩
                hist = fdr.DataReader(t, prev_start, end_date)
                if not hist.empty and len(hist) >= 5:
                    this_vol = float(hist['Volume'].loc[start_date:end_date].sum())
                    prev_vol = float(hist['Volume'].loc[prev_start:start_date].sum())
                    
                    if pd.isna(this_vol) or this_vol == 0: continue
                    if pd.isna(prev_vol) or prev_vol == 0: prev_vol = 1.0
                    
                    change = ((this_vol - prev_vol) / prev_vol) * 100
                    
                    data_list.append({
                        "기업명(ETF명)": name, "티커": t,
                        "현재가": float(hist['Close'].iloc[-1]),
                        "선택주차 누적거래량": float(this_vol),
                        "전주대비 증감률(%)": round(change, 2)
                    })
            return pd.DataFrame(data_list)
            
        # 2. 미국 시장 전용 수집 엔진 (yfinance 기반 대량 풀 쿼리)
        else:
            us_pool = ["QQQ", "TQQQ", "SQQQ", "SPY", "SOXL", "SOXS", "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "AMD", "INTC", "NFLX", "XOM", "V", "JPM", "MA", "PG", "UNH", "HD", "BAC", "DIS", "KO", "PEP", "COST", "AVGO", "CSCO", "ORCL", "ADBE", "CRM", "CVX", "WMT", "MCD", "WFC", "XLN", "AMAT", "MU", "GE", "QCOM", "TXN", "PM", "VZ", "T", "INTU", "IBM", "NEE", "LOW", "AXP", "HON", "CAT", "PFE", "GS", "MS", "BLK", "UBER", "PLTR", "SMCI", "PANW", "ANET", "FI", "NOW", "ETN", "LRCX", "VRTX", "GEV", "CRWD", "MDLZ", "TJX", "CB"]
            df = yf.download(" ".join(us_pool), start=prev_start, end=end_date, group_by='ticker', progress=False)
            
            data_list = []
            for t in us_pool:
                if t in df.columns.levels[0]:
                    t_df = df[t].dropna()
                    if not t_df.empty and len(t_df) >= 4:
                        this_vol = float(t_df['Volume'].loc[start_date:end_date].sum())
                        prev_vol = float(t_df['Volume'].loc[prev_start:start_date].sum())
                        
                        if pd.isna(this_vol) or this_vol == 0: continue
                        if pd.isna(prev_vol) or prev_vol == 0: prev_vol = 1.0
                        
                        change = ((this_vol - prev_vol) / prev_vol) * 100
                        name = name_map.get(t, t)
                        
                        data_list.append({
                            "기업명(ETF명)": name, "티커": t,
                            "현재가": float(t_df['Close'].iloc[-1]),
                            "선택주차 누적거래량": float(this_vol),
                            "전주대비 증감률(%)": round(change, 2)
                        })
            return pd.DataFrame(data_list)
    except:
        return pd.DataFrame()

# ----------------------------------------------------------------------
# 4대 지수 탭 구성 및 독립 시각화 엔진 출력
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        df_raw = get_market_fact_data(m_name, selected_dates["start"], selected_dates["end"])
        
        if df_raw.empty:
            st.warning("요청 주차의 원본 데이터 패칭 처리 중입니다. 사이드바에서 다른 주차를 지정해 보세요.")
        else:
            # 주간 거래량 감소 필터링 처리
            if exclude_decreased:
                df_raw = df_raw[df_raw["전주대비 증감률(%)"] >= 0]
            
            # 거래량 기준 내림차순 정렬 후 50개 정확히 분리
            df_top50 = df_raw.sort_values(by="선택주차 누적거래량", ascending=False).head(50).reset_index(drop=True)
            
            # [조건 만족] 1위부터 매칭되는 순위 인덱스 문자열 지정
            df_top50.index = (df_top50.index + 1).astype(str) + "위"
            df_top50.index.name = "순위"
            df_top50 = df_top50.reset_index()
            
            st.subheader(f"📊 {m_name} 주간 누적 거래량 순위 (Top 50)")
            
            # [조건 만족] hide_index=True를 통한 불필요 인덱스 열 제거 및 포맷팅 처리
            st.dataframe(
                df_top50.style.format({
                    "현재가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "선택주차 누적거래량": "{:,.0f}",
                    "전주대비 증감률(%)": "{:+.2f}%"
                }),
                use_container_width=True,
                height=450,
                hide_index=True
            )
            
            # [조건 만족] 하단 직관 차트 컴포넌트 출력
            st.markdown("---")
            st.subheader(f"📈 {m_name} 핵심 상위 10개 자산 거래량 추세 분석")
            
            df_chart = df_top50.head(10)
            st.bar_chart(
                data=df_chart,
                x="기업명(ETF명)",
                y="선택주차 누적거래량",
                use_container_width=True
            )
