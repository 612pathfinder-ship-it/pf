import streamlit as st
import pandas as pd
import yfinance as yf
from pykrx import stock
from datetime import datetime, timedelta

# 페이지 기본 설정
st.set_page_config(layout="wide", page_title="Volume Top 50 Dashboard")
st.title("📊 4대 지수 거래량 상위 50 분석 대시보드")
st.caption("S&P 500, NASDAQ, KOSPI, KOSDAQ 직전 3개월 주차별 팩트 데이터 분석")

# ----------------------------------------------------------------------
# [팩트 기반] 직전 3개월 주차별 날짜 매핑 데이터 생성 (월요일~금요일 기준)
# ----------------------------------------------------------------------
def generate_weekly_options():
    """직전 3개월 내의 모든 주차별 [시작일, 종료일]을 생성하는 함수"""
    options = {}
    today = datetime.today()
    
    # 안전하게 오늘부터 역산하여 14주(약 3개월) 분량의 주차 계산
    for i in range(14):
        # 해당 주차의 월요일과 금요일 계산
        monday = today - timedelta(days=today.weekday() + (i * 7))
        friday = monday + timedelta(days=4)
        
        # 미래의 데이터는 생성하지 않음
        if monday > datetime.today():
            continue
            
        # UI에 표시할 포맷 (예: "2026년 06월 4주차 (06.22 ~ 06.26)")
        month_str = monday.strftime("%m")
        week_num = (monday.day - 1) // 7 + 1
        label = f"{monday.strftime('%Y년')} {month_str}월 {week_num}주차 ({monday.strftime('%m.%d')} ~ {friday.strftime('%m.%d')})"
        
        options[label] = {
            "start_kr": monday.strftime("%Y%m%d"),
            "end_kr": friday.strftime("%Y%m%d"),
            "start_us": monday.strftime("%Y-%m-%d"),
            "end_us": friday.strftime("%Y-%m-%d")
        }
    return options

# 주차 선택 드롭다운 풀 생성
weekly_options = generate_weekly_options()

# ----------------------------------------------------------------------
# 사이드바 제어 설정 (드롭다운 기능 추가)
# ----------------------------------------------------------------------
st.sidebar.header("🔧 대시보드 제어판")

# 드롭다운 형식으로 원하는 주차 선택 가능 (기본값은 항상 가장 최신 최근 주차)
selected_week_label = st.sidebar.selectbox("조회할 주차 선택 (직전 3개월)", list(weekly_options.keys()))
selected_dates = weekly_options[selected_week_label]

exclude_decreased = st.sidebar.checkbox("주단위 거래량 감소 종목 제외", value=False)

st.sidebar.info(f"선택된 조회 기간:\n{selected_dates['start_us']} ~ {selected_dates['end_us']}")

# ----------------------------------------------------------------------
# 데이터 로드 함수 (선택된 날짜 기반 팩트 추출)
# ----------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_us_volume_data(tickers, start_date, end_date):
    """미국 주식 선택 기간 거래량 및 직전 기간 대비 증감률 산출"""
    data_list = []
    tickers_str = " ".join(tickers[:100])
    
    # 직전 주 데이터 비교를 위해 조회 시작일을 2주일 전으로 확장
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    extended_start = (st_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    
    try:
        df = yf.download(tickers_str, start=extended_start, end=end_date, group_by='ticker', progress=False)
        
        for ticker in tickers[:100]:
            if ticker in df.columns.levels[0]:
                t_df = df[ticker].dropna()
                if len(t_df) >= 3:
                    # 해당 주차의 마지막 날 거래량
                    daily_vol = t_df['Volume'].iloc[-1]
                    
                    # 해당 주차 평균 거래량 vs 직전 주차 평균 거래량
                    this_week_avg = t_df['Volume'].loc[start_date:end_date].mean()
                    prev_week_avg = t_df['Volume'].loc[extended_start:start_date].mean()
                    
                    if pd.isna(this_week_avg): this_week_avg = 0
                    if pd.isna(prev_week_avg) or prev_week_avg == 0: prev_week_avg = 1
                    
                    weekly_change = ((this_week_avg - prev_week_avg) / prev_week_avg) * 100
                    
                    data_list.append({
                        "티커": ticker,
                        "해당주차종가": t_df['Close'].iloc[-1],
                        "주차말일거래량": int(daily_vol),
                        "선택주차평균거래량": int(this_week_avg),
                        "주간거래량증감(%)": round(weekly_change, 2)
                    })
    except Exception:
        pass
    return pd.DataFrame(data_list)

@st.cache_data(ttl=3600)
def get_kr_volume_data(market_code, start_date, end_date):
    """한국 주식 선택 기간 누적 거래량 및 직전 주 대비 증감률 산출"""
    st_dt = datetime.strptime(start_date, "%Y%m%d")
    prev_start = (st_dt - timedelta(days=7)).strftime("%Y%m%d")
    
    try:
        # 선택한 주차 기간의 누적 데이터
        df_this_week = stock.get_market_price_change_by_ticker(start_date, end_date, market_code)
        # 직전 주차 기간의 누적 데이터 (비교용)
        df_prev_week = stock.get_market_price_change_by_ticker(prev_start, start_date, market_code)
        
        if df_this_week.empty:
            # 해당 날짜 데이터가 아직 없으면(예: 데이터 미생성 휴일) 에러 방지용 역산
            return pd.DataFrame()
            
        data_list = []
        for ticker in df_this_week.index[:150]:
            name = stock.get_market_ticker_name(ticker)
            
            this_week_vol = df_this_week.loc[ticker, '거래량'] if ticker in df_this_week.index else 0
            prev_week_vol = df_prev_week.loc[ticker, '거래량'] if ticker in df_prev_week.index else 0
            
            weekly_change = ((this_week_vol - prev_week_vol) / prev_week_vol) * 100 if prev_week_vol > 0 else 0
            
            data_list.append({
                "종목명": name,
                "티커": ticker,
                "해당주차종가": df_this_week.loc[ticker, '종가'] if ticker in df_this_week.index else 0,
                "선택주차누적거래량": int(this_week_vol),
                "주간거래량증감(%)": round(weekly_change, 2)
            })
        return pd.DataFrame(data_list)
    except Exception:
        return pd.DataFrame()

# ----------------------------------------------------------------------
# 메인 대시보드 뷰 구성
# ----------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"])

def display_dashboard(df_data, is_kr=False):
    if df_data.empty:
        st.warning("선택하신 기간의 거래소 팩트 데이터가 존재하지 않거나 호출 범위 제한을 초과했습니다. 다른 주차를 선택해 주세요.")
        return
    
    # 감소 종목 필터링 팩트 적용
    if exclude_decreased:
        df_data = df_data[df_data["주간거래량증감(%)"] >= 0]
        
    sort_key = "선택주차누적거래량" if is_kr else "선택주차평균거래량"
    vol_label = "주차말일거래량" if not is_kr else "선택주차누적거래량"
    
    st.subheader(f"📅 {selected_week_label} 거래량 상위 50위")
    
    # 지정 정렬 기준에 따라 상위 50위 소팅
    df_result = df_data.sort_values(by=sort_key, ascending=False).head(50).reset_index(drop=True)
    st.dataframe(df_result, use_container_width=True)

# 샘플 데이터 인덱스 매핑 풀
sp500_tickers = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "AMD", "INTC", "NFLX"]
nasdaq_tickers = ["QQQ", "AVGO", "COST", "PEP", "ADBE", "CMCSA", "TMUS", "TXN", "AMAT", "QCOM"]

with tab1:
    df_sp = get_us_volume_data(sp500_tickers, selected_dates["start_us"], selected_dates["end_us"])
    display_dashboard(df_sp, is_kr=False)

with tab2:
    df_nd = get_us_volume_data(nasdaq_tickers, selected_dates["start_us"], selected_dates["end_us"])
    display_dashboard(df_nd, is_kr=False)

with tab3:
    df_kospi = get_kr_volume_data("STK", selected_dates["start_kr"], selected_dates["end_kr"])
    display_dashboard(df_kospi, is_kr=True)

with tab4:
    df_kosdaq = get_kr_volume_data("KSQ", selected_dates["start_kr"], selected_dates["end_kr"])
    display_dashboard(df_kosdaq, is_kr=True)
