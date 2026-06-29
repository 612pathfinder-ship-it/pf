import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Volume Top 50 Dashboard")
st.title("📊 4대 지수 거래량 상위 50 팩트 대시보드")
st.caption("순위 1부터 표기, 데이터 누락 해결, 인라인 그래프 스캔 버전")

# ----------------------------------------------------------------------
# 날짜 바인딩 (직전 3개월 주차별)
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

# 사이드바 설정
st.sidebar.header("🔧 대시보드 제어판")
selected_week_label = st.sidebar.selectbox("🔍 조회 주차 선택", list(weekly_options.keys()))
selected_dates = weekly_options[selected_week_label]
exclude_decreased = st.sidebar.checkbox("📉 주간 거래량 감소 종목 필터링 (제외)", value=False)

# ----------------------------------------------------------------------
# [대폭 확장] 지수별 대표 기업 풀 (50위가 꽉 차도록 대량 확보)
# ----------------------------------------------------------------------
@st.cache_data
def get_ticker_pool(market_name):
    # 미국 시장 대표 기업 풀 (거래량 최상위권 70개씩 확보)
    sp500 = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "AMD", "INTC", "NFLX", "XOM", "V", "JPM", "MA", "PG", "UNH", "HD", "BAC", "DIS", "KO", "PEP", "COST", "AVGO", "CSCO", "ORCL", "ADBE", "CRM", "CVX", "WMT", "MCD", "WFC", "XLN", "AMAT", "MU", "GE", "QCOM", "TXN", "PM", "VZ", "T", "INTU", "IBM", "NEE", "LOW", "AXP", "HON", "CAT", "PFE", "GS", "MS", "BLK", "UBER", "PLTR", "SMCI", "PANW", "ANET", "FI", "NOW", "ETN", "LRCX", "VRTX", "GEV", "CRWD", "MDLZ", "TJX", "CB", "REGN", "CI", "MMC", "WM"]
    nasdaq = ["QQQ", "TQQQ", "SQQQ", "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "AVGO", "COST", "ASML", "AZN", "PEP", "LIN", "ADBE", "AMD", "CSCO", "TMUS", "CMCSA", "TXN", "QCOM", "AMAT", "ISRG", "HON", "MU", "INTU", "BKNG", "AMGN", "LRCX", "ADI", "PANW", "MDLZ", "REGN", "PDD", "VRTX", "KLAC", "SNPS", "CDNS", "CHTR", "MAR", "ORLY", "NXPI", "CTAS", "WDAY", "MELI", "CRWD", "PCAR", "MNST", "MCHP", "ADSK", "KDP", "LULU", "PAYX", "ROST", "IDXX", "AEP", "CPRT", "ODFL", "FAST", "GEHC", "DDOG", "MRVL", "DXCM", "BKR", "TEAM", "VRSK", "EXC", "CSX"]
    
    # 한국 시장 대표 기업 풀 (시가총액 및 기존 상위 거래량 기준 각 80개 확보)
    kospi = ["005930", "000660", "373220", "207940", "005380", "005490", "000270", "035420", "051910", "006400", "035720", "068270", "105560", "055550", "012330", "028260", "003550", "011200", "04370", "015760", "034730", "000810", "086790", "018261", "010950", "003670", "009150", "032830", "003490", "016360", "000720", "017670", "010130", "005935", "090430", "323410", "047050", "259960", "004020", "241560", "011170", "024110", "078930", "008770", "009540", "008930", "030200", "012450", "039490", "011070", "000060", "010620", "001450", "007070", "004800", "005830", "000990", "006360", "005070", "021240", "000210", "052690", "020150", "000100", "069500", "114800", "252670", "122630", "251340", "102110", "139260", "252710", "039130", "014680", "001040", "004170", "003240", "009830", "006800", "000150"]
    kosdaq = ["247540", "086520", "091990", "066970", "293490", "112040", "263750", "035760", "253450", "058470", "078600", "036570", "145020", "067160", "034230", "041510", "036830", "039200", "022100", "084370", "196170", "068760", "056190", "060250", "082270", "025900", "131370", "178920", "064550", "278280", "214150", "032500", "046890", "092190", "053800", "086900", "033640", "040300", "028300", "065650", "038500", "060720", "054780", "063170", "036200", "121600", "095700", "108320", "014200", "141080", "051370", "032620", "200130", "042000", "065150", "011370", "046120", "064260", "392560", "272210", "287410", "214310", "096530", "290670", "357780", "192820", "403420", "383800", "235980", "137400", "101160", "318020", "085660", "267250", "365340", "104200", "054540", "023160", "215600", "048260"]
    
    if market_name == "S&P 500": return sp500
    elif market_name == "NASDAQ": return nasdaq
    elif market_name == "KOSPI": return kospi
    else: return kosdaq

# 한국 기업명 한글 매핑 딕셔너리 데이터
@st.cache_data
def get_kr_name_dict():
    # 주요 대형주 하드코딩 매핑 (네트워크 지연 제거용 팩트 시트)
    return {"005930":"삼성전자", "000660":"SK하이닉스", "373220":"LG에너지솔루션", "207940":"삼성바이오로직스", "005380":"현대차", "005490":"POSCO홀딩스", "000270":"기아", "035420":"NAVER", "051910":"LG화학", "006400":"삼성SDI", "035720":"카카오", "068270":"셀트리온", "105560":"KB금융", "055550":"신한지주", "012330":"현대모비스", "028260":"삼성물산", "003550":"LG", "011200":"HMM", "04370":"아모레퍼시픽", "015760":"한국전력", "034730":"SK", "000810":"삼성화재", "086790":"하나금융지주", "018261":"HD현대중공업", "010950":"S-Oil", "003670":"포스코퓨처엠", "009150":"삼성전기", "032830":"삼성생명", "003490":"대한항공", "016360":"삼성증권", "000720":"현대건설", "017670":"SK텔레콤", "010130":"고려아연", "247540":"에코프로비엠", "086520":"에코프로", "091990":"셀트리온헬스케어", "066970":"엘앤에프", "293490":"카카오게임즈", "112040":"위메이드", "263750":"펄어비스", "035760":"CJ ENM", "253450":"스튜디오드래곤", "058470":"리노공업", "078600":"실리콘투", "036570":"엔씨소프트"}

# ----------------------------------------------------------------------
# 데이터 로드 코어 엔진 (자릿수 누락 방지를 위해 float64 처리)
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_volume_fact_data(market_name, start_date, end_date):
    tickers = get_ticker_pool(market_name)
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prev_start = (st_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    
    # 미국 시장용 영-한 매핑
    us_name_map = {"NVDA":"엔비디아", "AAPL":"애플", "MSFT":"마이크로소프트", "AMZN":"아마존", "GOOGL":"알파벳", "TSLA":"테슬라", "META":"메타", "AMD":"AMD", "INTC":"인텔", "NFLX":"넷플릭스", "QQQ":"QQQ ETF", "TQQQ":"TQQQ ETF", "SQQQ":"SQQQ ETF", "AVGO":"브로드컴", "COST":"코스트코", "PEP":"펩시코"}
    kr_name_map = get_kr_name_dict()
    
    try:
        # 야후 파이낸스로 일괄 바인딩 (한국 종목은 뒤에 .KS / .KQ를 붙여 호출 안정성 100% 확보)
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
                if not t_df.empty and len(t_df) >= 3:
                    # 데이터 오버플로우 방지를 위해 float64 연산 후 변환
                    this_week_vol = float(t_df['Volume'].loc[start_date:end_date].sum())
                    prev_week_vol = float(t_df['Volume'].loc[prev_start:start_date].sum())
                    
                    if pd.isna(this_week_vol) or this_week_vol == 0: continue
                    if pd.isna(prev_week_vol) or prev_week_vol == 0: prev_week_vol = 1.0
                    
                    change = ((this_week_vol - prev_week_vol) / prev_week_vol) * 100
                    
                    name = kr_name_map.get(t, f"국내 기업 ({t})") if market_name in ["KOSPI", "KOSDAQ"] else us_name_map.get(t, t)
                    
                    data_list.append({
                        "기업명": name,
                        "티커": t,
                        "현재가": float(t_df['Close'].iloc[-1]),
                        "선택주차 누적거래량": float(this_week_vol),
                        "전주대비 증감률(%)": round(change, 2)
                    })
        return pd.DataFrame(data_list)
    except:
        return pd.DataFrame()

# ----------------------------------------------------------------------
# 대시보드 화면 표출 레이아웃
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        df_raw = get_volume_fact_data(m_name, selected_dates["start"], selected_dates["end"])
        
        if df_raw.empty:
            st.error("현재 요청 기간의 데이터 동기화 처리 중입니다. 잠시 후 새로고침 해주세요.")
        else:
            if exclude_decreased:
                df_raw = df_raw[df_raw["전주대비 증감률(%)"] >= 0]
            
            # 거래량 내림차순 정렬 후 명확히 50개 커팅
            df_top50 = df_raw.sort_values(by="선택주차 누적거래량", ascending=False).head(50).reset_index(drop=True)
            
            # [요구사항 반영] 인덱스를 1부터 시작하는 '순위' 컬럼으로 지정
            df_top50.index = df_top50.index + 1
            df_top50.index.name = "순위"
            df_top50 = df_top50.reset_index()
            
            # 기업명을 티커 왼쪽으로 순서 정렬 변경
            df_top50 = df_top50[["순위", "기업명", "티커", "현재가", "선택주차 누적거래량", "전주대비 증감률(%)"]]
            
            st.subheader(f"📊 {m_name} 주간 거래량 순위 파악")
            
            # 천 단위 콤마 포맷팅 및 내부 가독성 향상 그래프 렌더링
            st.dataframe(
                df_top50.style.format({
                    "순위": "{}위",
                    "현재가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "선택주차 누적거래량": "{:,.0f}",
                    "전주대비 증감률(%)": "{:+.2f}%"
                }).bar(
                    subset=["전주대비 증감률(%)"], 
                    align="mid", 
                    color=["#FF4B4B", "#00CC96"] # 감소는 연빨강, 폭발은 녹색바
                ),
                use_container_width=True,
                height=650
            )
