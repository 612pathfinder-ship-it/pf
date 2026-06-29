import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 기본 설정 및 와이드 레이아웃 강제
st.set_page_config(layout="wide", page_title="Volume Top 50 Dashboard")
st.title("📊 4대 지수 거래량 상위 50 판단 대시보드")
st.caption("인덱스 제거, 주간 거래량 추세 그래프, ETF명 매핑 최종 완결판")

# ----------------------------------------------------------------------
# [검증 완해] 날짜 바인딩 (직전 3개월 주차별 리스트 스냅샷 생성)
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

# 사이드바 제어 설정
st.sidebar.header("🔧 대시보드 제어판")
selected_week_label = st.sidebar.selectbox("🔍 조회 주차 선택", list(weekly_options.keys()))
selected_dates = weekly_options[selected_week_label]
exclude_decreased = st.sidebar.checkbox("📉 주간 거래량 감소 종목 필터링 (제외)", value=False)

# ----------------------------------------------------------------------
# [데이터 유실 방지] 지수별 핵심 대표 자산 및 주요 거래량 상위 ETF 풀 확장
# ----------------------------------------------------------------------
@st.cache_data
def get_ticker_pool(market_name):
    sp500 = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "AMD", "INTC", "NFLX", "XOM", "V", "JPM", "MA", "PG", "UNH", "HD", "BAC", "DIS", "KO", "PEP", "COST", "AVGO", "CSCO", "ORCL", "ADBE", "CRM", "CVX", "WMT", "MCD", "WFC", "XLN", "AMAT", "MU", "GE", "QCOM", "TXN", "PM", "VZ", "T", "INTU", "IBM", "NEE", "LOW", "AXP", "HON", "CAT", "PFE", "GS", "MS", "BLK", "UBER", "PLTR", "SMCI", "PANW", "ANET", "FI", "NOW", "ETN", "LRCX", "VRTX", "GEV", "CRWD", "MDLZ", "TJX", "CB", "REGN", "CI", "MMC", "WM"]
    nasdaq = ["QQQ", "TQQQ", "SQQQ", "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "AVGO", "COST", "ASML", "AZN", "PEP", "LIN", "ADBE", "AMD", "CSCO", "TMUS", "CMCSA", "TXN", "QCOM", "AMAT", "ISRG", "HON", "MU", "INTU", "BKNG", "AMGN", "LRCX", "ADI", "PANW", "MDLZ", "REGN", "PDD", "VRTX", "KLAC", "SNPS", "CDNS", "CHTR", "MAR", "ORLY", "NXPI", "CTAS", "WDAY", "MELI", "CRWD", "PCAR", "MNST", "MCHP", "ADSK", "KDP", "LULU", "PAYX", "ROST", "IDXX", "AEP", "CPRT", "ODFL", "FAST", "GEHC", "DDOG", "MRVL", "DXCM", "BKR", "TEAM", "VRSK", "EXC", "CSX"]
    kospi = ["005930", "000660", "373220", "207940", "005380", "005490", "000270", "035420", "051910", "006400", "035720", "068270", "105560", "055550", "012330", "028260", "003550", "011200", "04370", "015760", "034730", "000810", "086790", "018261", "010950", "003670", "009150", "032830", "003490", "016360", "000720", "017670", "010130", "005935", "090430", "323410", "047050", "259960", "004020", "241560", "011170", "024110", "078930", "008770", "009540", "008930", "030200", "012450", "039490", "011070", "000060", "010620", "001450", "007070", "004800", "005830", "000990", "006360", "005070", "021240", "000210", "052690", "020150", "000100", "069500", "114800", "252670", "122630", "251340", "102110", "139260", "252710", "039130", "014680", "001040", "004170", "003240", "009830", "006800", "000150"]
    kosdaq = ["247540", "086520", "091990", "066970", "293490", "112040", "263750", "035760", "253450", "058470", "078600", "036570", "145020", "067160", "034230", "041510", "036830", "039200", "022100", "084370", "196170", "068760", "056190", "060250", "082270", "025900", "131370", "178920", "064550", "278280", "214150", "032500", "046890", "092190", "053800", "086900", "033640", "040300", "028300", "065650", "038500", "060720", "054780", "063170", "036200", "121600", "095700", "108320", "014200", "141080", "051370", "032620", "200130", "042000", "065150", "011370", "046120", "064260", "392560", "272210", "287410", "214310", "096530", "290670", "357780", "192820", "403420", "383800", "235980", "137400", "101160", "318020", "085660", "267250", "365340", "104200", "054540", "023160", "215600", "048260"]
    
    if market_name == "S&P 500": return sp500
    elif market_name == "NASDAQ": return nasdaq
    elif market_name == "KOSPI": return kospi
    else: return kosdaq

# ETF 상품 및 대형 기업 마스터 명칭 맵 (줄바꿈 오류 완벽 교정)
@st.cache_data
def get_master_name_map():
    return {
        "NVDA":"엔비디아", "AAPL":"애플", "MSFT":"마이크로소프트", "AMZN":"아마존", "GOOGL":"알파벳", "TSLA":"테슬라", "META":"메타", "AMD":"AMD", "INTC":"인텔", "NFLX":"넷플릭스",
        "QQQ":"Invesco QQQ (나스닥100 ETF)", "TQQQ":"ProShares 나스닥 3배 레버리지 ETF", "SQQQ":"ProShares 나스닥 3배 인버스 ETF", "AVGO":"브로드컴", "COST":"코스트코", "PEP":"펩시코",
        "005930":"삼성전자", "000660":"SK하이닉스", "373220":"LG에너지솔루션", "207940":"삼성바이오로직스", "005380":"현대차", "00
