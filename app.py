import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 기본 설정 및 와이드 레이아웃 강제
st.set_page_config(layout="wide", page_title="Volume Top 50 Dashboard")
st.title("📊 4대 지수 거래량 상위 50 판단 대시보드")
st.caption("인덱스 제거, 주간 거래량 추세 그래프, ETF명 매핑 최종 완결판")

# ----------------------------------------------------------------------
# 날짜 바인딩 (직전 3개월 주차별 리스트 스냅샷 생성)
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
            "end": python_date := friday.strftime("%Y-%m-%d")
        }
    return options

weekly_options = get_cached_weeks()

# 사이드바 제어 설정
st.sidebar.header("🔧 대시보드 제어판")
selected_week_label = st.sidebar.selectbox("🔍 조회 주차 선택", list(weekly_options.keys()))
selected_dates = weekly_options[selected_week_label]
exclude_decreased = st.sidebar.checkbox("📉 주간 거래량 감소 종목 필터링 (제외)", value=False)

# ----------------------------------------------------------------------
# 지수별 대표 기업 및 주요 거래량 상위 ETF 풀 확장
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

# ----------------------------------------------------------------------
# [구조 전면 개편] 에러 방지를 위해 종목당 한 줄씩 세로 배치 처리
# ----------------------------------------------------------------------
@st.cache_data
def get_master_name_map():
    m_map = {}
    
    # 미국 주요 자산 및 지수물 ETF
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
    m_map["QQQ"] = "Invesco QQQ (나스닥100 ETF)"
    m_map["TQQQ"] = "ProShares 나스닥 3배 레버리지 ETF"
    m_map["SQQQ"] = "ProShares 나스닥 3배 인버스 ETF"
    m_map["AVGO"] = "브로드컴"
    m_map["COST"] = "코스트코"
    m_map["PEP"] = "펩시코"
    
    # 국내 주요 대형 자산 및 코스피/코스닥 대표 ETF
    m_map["005930"] = "삼성전자"
    m_map["000660"] = "SK하이닉스"
    m_map["373220"] = "LG에너지솔루션"
    m_map["207940"] = "삼성바이오로직스"
    m_map["005380"] = "현대차"
    m_map["005490"] = "POSCO홀딩스"
    m_map["000270"] = "기아"
    m_map["035420"] = "NAVER"
    m_map["069500"] = "KODEX 200 (코스피 대표 ETF)"
    m_map["114800"] = "KODEX 인버스 ETF"
    m_map["252670"] = "KODEX 200선물인버스2X ETF"
    m_map["122630"] = "KODEX 레버리지 ETF"
    m_map["251340"] = "KODEX 코스닥150선물인버스 ETF"
    m_map["102110"] = "TIGER 200 ETF"
    m_map["139260"] = "TIGER 200 경기소비재 ETF"
    m_map["252710"] = "TIGER 200선물인버스2X ETF"
    
    return m_map

# ----------------------------------------------------------------------
# 데이터 로드 코어 엔진
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_volume_fact_data(market_name, start_date, end_date):
    tickers = get_ticker_pool(market_name)
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prev_start = (st_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    name_map = get_master_name_map()
    
    try:
        formatted_tickers = []
        for t in tickers:
            if market_name == "KOSPI": formatted_tickers.append(f"{t}.KS")
            elif market_name == "KOSDAQ": formatted_tickers.append(f"{t}.KQ")
            else: formatted_tickers.append(t)
            
        df = yf.download(" ".join(formatted_tickers), start=prev_start, end=end_date, group_by='ticker', progress=False)
        
        data_list = []
        for t in tickers:
            lookup_key = f"{t}.KS" if market_name == "KOSPI" else (f"{t}.KQ" if market_name == "KOSDAQ" else t)
            
            if lookup_key in df.columns.levels[0]:
                t_df = df[lookup_key].dropna()
                if not t_df.empty and len(t_df) >= 5:
                    this_week_vol = float(t_df['Volume'].loc[start_date:end_date].sum())
                    prev_week_vol = float(t_df['Volume'].loc[prev_start:start_date].sum())
                    
                    if pd.isna(this_week_vol) or this_week_vol == 0: 
                        continue
                    if pd.isna(prev_week_vol) or prev_week_vol == 0: 
                        prev_week_vol = 1.0
                    
                    change = ((this_week_vol - prev_week_vol) / prev_week_vol) * 100
                    name = name_map.get(t, f"일반 자산 및 기업군 ({t})")
                    
                    data_list.append({
                        "기업명(ETF명)": name, "티커": t,
                        "현재가": float(t_df['Close'].iloc[-1]),
                        "선택주차 누적거래량": float(this_week_vol),
                        "전주대비 증감률(%)": round(change, 2)
                    })
        return pd.DataFrame(data_list)
    except:
        return pd.DataFrame()

# ----------------------------------------------------------------------
# 4대 지수 탭 및 차트 가독성 통합 인터페이스 구현
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        df_raw = get_volume_fact_data(m_name, selected_dates["start"], selected_dates["end"])
        
        if df_raw.empty:
            st.error("현재 자산의 거래 데이터 연산 범위 오류 혹은 휴장일입니다. 사이드바에서 다른 주차를 선택해 주세요.")
        else:
            if exclude_decreased:
                df_raw = df_raw[df_raw["전주대비 증감률(%)"] >= 0]
            
            # 거래량 가공 정렬 후 완벽하게 50개 리스팅 확보
            df_top50 = df_raw.sort_values(by="선택주차 누적거래량", ascending=False).head(50).reset_index(drop=True)
            
            # 인덱스를 수치 '순위' 컬럼으로 완전히 격상
            df_top50.index = (df_top50.index + 1).astype(str) + "위"
            df_top50.index.name = "순위"
            df_top50 = df_top50.reset_index()
            
            st.subheader(f"📊 {m_name} 주간 거래량 상위 Top 50 리스트")
            
            # [가독성 설정] hide_index=True 적용으로 0,1,2 기본 번호열 강제 삭제
            st.dataframe(
                df_top50.style.format({
                    "현재가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "선택주차 누적거래량": "{:,.0f}",
                    "전주대비 증감률(%)": "{:+.2f}%"
                }),
                use_container_width=True,
                height=420,
                hide_index=True
            )
            
            # [가독성 설정] 하단 전용 막대그래프 렌더링
            st.markdown("---")
            st.subheader(f"📈 {m_
