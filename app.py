import streamlit as st
import pandas as pd
import yfinance as yf
from pykrx import stock
from datetime import datetime, timedelta

# 페이지 기본 설정
st.set_page_config(layout="wide", page_title="Volume Top 50 Dashboard")
st.title("📊 4대 지수 거래량 상위 50 실시간 대시보드 (일단위/주단위)")
st.caption("S&P 500, NASDAQ, KOSPI, KOSDAQ 거래량 팩트 데이터 분석")

# ----------------------------------------------------------------------
# [안전장치] 한국 거래소 데이터 호출용 루프 함수
# ----------------------------------------------------------------------
def fetch_kr_market_data(market_code):
    """
    서버 시차 및 주말/공휴일로 인해 pykrx 내부에서 IndexError가 나는 것을 
    원천 차단하기 위해, 실제 데이터가 잡히는 영업일을 역추적하여 가져옵니다.
    """
    base_date = datetime.today()
    
    # 9시 이전 새벽/아침 시간대라면 전날 기점으로 시작
    if base_date.hour < 9:
        base_date -= timedelta(days=1)
        
    # 데이터 수집 성공할 때까지 최대 10일 전까지 역추적
    for i in range(10):
        target_date = (base_date - timedelta(days=i)).strftime('%Y%m%d')
        try:
            df = stock.get_market_price_change_by_ticker(target_date, target_date, market_code)
            if df is not None and not df.empty:
                # 이번주(최근 5영업일 가량), 지난주(그 전 5영업일 가량) 기준일 강제 계산
                this_week_start = (base_date - timedelta(days=i+7)).strftime('%Y%m%d')
                prev_week_start = (base_date - timedelta(days=i+14)).strftime('%Y%m%d')
                
                df_this_week = stock.get_market_price_change_by_ticker(this_week_start, target_date, market_code)
                df_prev_week = stock.get_market_price_change_by_ticker(prev_week_start, this_week_start, market_code)
                
                return df, df_this_week, df_prev_week
        except Exception:
            # 에러 발생 시 무시하고 다음 날짜(전날)로 넘어가 재시도
            continue
            
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# ----------------------------------------------------------------------
# 데이터 로드 함수 (미국: yfinance / 한국: 커스텀 루프 활용)
# ----------------------------------------------------------------------
@st.cache_data(ttl=3600)  # 1시간 단위 캐싱
def get_us_volume_data(tickers):
    """미국 주식(S&P500, NASDAQ 주요 종목)의 일단위/주단위 거래량 추출"""
    today_str = datetime.today().strftime('%Y-%m-%d')
    two_weeks_ago_str = (datetime.today() - timedelta(days=14)).strftime('%Y-%m-%d')
    
    data_list = []
    tickers_str = " ".join(tickers[:100])
    df = yf.download(tickers_str, start=two_weeks_ago_str, end=today_str, group_by='ticker', progress=False)
    
    for ticker in tickers[:100]:
        if ticker in df.columns.levels[0]:
            t_df = df[ticker].dropna()
            if len(t_df) >= 10:
                daily_vol = t_df['Volume'].iloc[-1]
                prev_daily_vol = t_df['Volume'].iloc[-2]
                daily_change = ((daily_vol - prev_daily_vol) / prev_daily_vol) * 100 if prev_daily_vol > 0 else 0
                
                this_week_avg = t_df['Volume'].iloc[-5:].mean()
                prev_week_avg = t_df['Volume'].iloc[-10:-5].mean()
                weekly_change = ((this_week_avg - prev_week_avg) / prev_week_avg) * 100 if prev_week_avg > 0 else 0
                
                data_list.append({
                    "티커": ticker,
                    "현재가": t_df['Close'].iloc[-1],
                    "당일거래량": int(daily_vol),
                    "전일대비(%)": round(daily_change, 2),
                    "이번주평균거래량": int(this_week_avg),
                    "주간거래량증감(%)": round(weekly_change, 2)
                })
    return pd.DataFrame(data_list)

@st.cache_data(ttl=3600)
def get_kr_volume_data(market_code):
    """안전장치가 강화된 한국 주식(KOSPI 또는 KOSDAQ) 거래량 추출"""
    df_today, df_this_week, df_prev_week = fetch_kr_market_data(market_code)
    
    if df_today.empty:
        return pd.DataFrame()

    data_list = []
    # 데이터 왜곡을 방지하기 위해 오늘 실제로 거래가 기록된 종목 리스트 기준으로 순회
    for ticker in df_today.index[:150]: 
        name = stock.get_market_ticker_name(ticker)
        
        daily_vol = df_today.loc[ticker, '거래량'] if ticker in df_today.index else 0
        this_week_vol = df_this_week.loc[ticker, '거래량'] if ticker in df_this_week.index else 0
        prev_week_vol = df_prev_week.loc[ticker, '거래량'] if ticker in df_prev_week.index else 0
        
        weekly_change = ((this_week_vol - prev_week_vol) / prev_week_vol) * 100 if prev_week_vol > 0 else 0
        
        data_list.append({
            "종목명": name,
            "티커": ticker,
            "현재가": df_today.loc[ticker, '종가'] if ticker in df_today.index else 0,
            "당일거래량": int(daily_vol),
            "이번주누적거래량": int(this_week_vol),
            "주간거래량증감(%)": round(weekly_change, 2)
        })
        
    return pd.DataFrame(data_list)

# ----------------------------------------------------------------------
# 사이드바 제어 플러그인 (주간 거래량 감소 종목 필터링 스위치)
# ----------------------------------------------------------------------
st.sidebar.header("🔧 대시보드 필터 설정")
exclude_decreased = st.sidebar.checkbox("주단위 거래량 감소 종목 제외", value=False)

# 샘플 티커 데이터 정의
sp500_tickers = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "AMD", "INTC", "NFLX"]
nasdaq_tickers = ["QQQ", "AVGO", "COST", "PEP", "ADBE", "CMCSA", "TMUS", "TXN", "AMAT", "QCOM"]

# ----------------------------------------------------------------------
# 메인 대시보드 화면 구성 (4개 지수 탭 분할)
# ----------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"])

def display_dashboard(df_data, is_kr=False):
    if df_data.empty:
        st.warning("현재 장이 열리지 않았거나 거래 데이터를 불러오는 중입니다. 잠시 후 새로고침 해주세요.")
        return
    
    # 1단계 필터: 주단위 거래량 감소 종목 빼기 처리
    if exclude_decreased:
        df_data = df_data[df_data["주간거래량증감(%)"] >= 0]
        
    # 일단위 거래량 상위 50 정렬 및 추출
    st.subheader("📆 일단위 거래량 상위 50위")
    df_daily = df_data.sort_values(by="당일거래량", ascending=False).head(50).reset_index(drop=True)
    st.dataframe(df_daily, use_container_width=True)
    
    # 주단위 거래량 상위 50 정렬 및 추출
    st.subheader("📅 주단위 거래량 상위 50위")
    sort_key = "이번주누적거래량" if is_kr else "이번주평균거래량"
    df_weekly = df_data.sort_values(by=sort_key, ascending=False).head(50).reset_index(drop=True)
    st.dataframe(df_weekly, use_container_width=True)

# 각 탭에 팩트 데이터 매핑 시 구동
with tab1:
    df_sp = get_us_volume_data(sp500_tickers)
    display_dashboard(df_sp, is_kr=False)

with tab2:
    df_nd = get_us_volume_data(nasdaq_tickers)
    display_dashboard(df_nd, is_kr=False)

with tab3:
    df_kospi = get_kr_volume_data("STK")
    display_dashboard(df_kospi, is_kr=True)

with tab4:
    df_kosdaq = get_kr_volume_data("KSQ")
    display_dashboard(df_kosdaq, is_kr=True)
