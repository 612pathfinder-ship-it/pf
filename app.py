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
# [추가된 로직] 최근 영업일(장 열린 날) 구하기 함수
# ----------------------------------------------------------------------
def get_latest_business_day():
    """주말이나 공휴일, 장 시작 전일 경우 가장 최근에 마감된 영업일 날짜를 반환"""
    dt = datetime.today()
    # 만약 오전 9시 전이라면 전날 데이터나 그 전 영업일 데이터를 보도록 유도
    if dt.hour < 9:
        dt = dt - timedelta(days=1)
        
    # 요일 체크 (5: 토요일, 6: 일요일) -> 금요일로 강제 이동
    while dt.weekday() >= 5:
        dt = dt - timedelta(days=1)
        
    return dt

# ----------------------------------------------------------------------
# 데이터 로드 함수 (미국: yfinance / 한국: pykrx 사용)
# ----------------------------------------------------------------------
@st.cache_data(ttl=3600)  # 1시간 단위 캐싱
def get_us_volume_data(tickers):
    """미국 주식(S&P500, NASDAQ 주요 종목)의 일단위/주단위 거래량 추출"""
    latest_day = get_latest_business_day()
    today_str = latest_day.strftime('%Y-%m-%d')
    two_weeks_ago_str = (latest_day - timedelta(days=14)).strftime('%Y-%m-%d')
    
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
    """한국 주식(KOSPI 또는 KOSDAQ) 거래량 추출 (휴일 에러 방지 반영)"""
    # 안전한 최근 영업일 기준 날짜 계산
    latest_day = get_latest_business_day()
    
    today = latest_day.strftime('%Y%m%d')
    one_week_ago = (latest_day - timedelta(days=7)).strftime('%Y%m%d')
    two_weeks_ago = (latest_day - timedelta(days=14)).strftime('%Y%m%d')
    
    # pykrx 내부 에러 방지를 위해 실제 장이 열렸던 날짜로 보정 시도
    try:
        today = stock.get_nearest_business_day_in_a_week(today)
        one_week_ago = stock.get_nearest_business_day_in_a_week(one_week_ago)
        two_weeks_ago = stock.get_nearest_business_day_in_a_week(two_weeks_ago)
    except Exception:
        # 안전장치: 혹시라도 공휴일 계산에서 에러가 또 나면 기본 날짜 유지
        pass
        
    # 당일 기준 시장 전체 거래량 조회
    df_today = stock.get_market_price_change_by_ticker(today, today, market_code)
    df_this_week = stock.get_market_price_change_by_ticker(one_week_ago, today, market_code)
    df_prev_week = stock.get_market_price_change_by_ticker(two_weeks_ago, one_week_ago, market_code)
    
    data_list = []
    # 에러 방지용 빈 데이터프레임 체크
    if df_today.empty:
        return pd.DataFrame()

    for ticker in df_today.index[:150]: # 거래량 상위 매칭용 기본 풀
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
