import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# 페이지 기본 설정
st.set_page_config(layout="wide", page_title="Market Interest Dashboard")
st.title("🎯 주간 거래량 기반 시장 관심도 추적 대시보드")
st.caption("거래대금/관심도 폭발 및 급감 종목을 발라내어 진입 및 탈출 타이밍을 판단하는 팩트 시트")

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
            "end": monday.strftime("%Y-%m-%d"), # 일주일 계산용 기점
            "label_period": f"{monday.strftime('%Y-%m-%d')} ~ {friday.strftime('%Y-%m-%d')}"
        }
    return options

weekly_options = get_cached_weeks()

# 사이드바 제어판
st.sidebar.header("🔧 대시보드 제어판")
selected_week_label = st.sidebar.selectbox("🔍 조회 주차 선택", list(weekly_options.keys()))
selected_dates = weekly_options[selected_week_label]
exclude_decreased = st.sidebar.checkbox("📉 주간 거래량 감소 종목 필터링 (제외)", value=False)

# ----------------------------------------------------------------------
# 마스터 자산 데이터 풀 생성
# ----------------------------------------------------------------------
@st.cache_data
def get_ticker_pool(market_name):
    sp500 = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "AMD", "INTC", "NFLX", "XOM", "V", "JPM", "MA", "PG", "UNH", "HD", "BAC", "DIS", "KO", "PEP", "COST", "AVGO", "CSCO", "ORCL", "ADBE", "CRM", "CVX", "WMT", "MCD", "WFC", "XLN", "AMAT", "MU", "GE", "QCOM", "TXN", "PM", "VZ", "T", "INTU", "IBM", "NEE", "LOW", "AXP", "HON", "CAT", "PFE", "GS", "MS", "BLK", "UBER", "PLTR", "SMCI", "PANW", "ANET", "FI", "NOW", "ETN", "LRCX", "VRTX", "GEV", "CRWD", "MDLZ", "TJX", "CB"]
    nasdaq = ["QQQ", "TQQQ", "SQQQ", "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "AVGO", "COST", "ASML", "AZN", "PEP", "LIN", "ADBE", "AMD", "CSCO", "TMUS", "CMCSA", "TXN", "QCOM", "AMAT", "ISRG", "HON", "MU", "INTU", "BKNG", "AMGN", "LRCX", "ADI", "PANW", "MDLZ", "REGN", "PDD", "VRTX", "KLAC", "SNPS", "CDNS", "CHTR", "MAR", "ORLY", "NXPI", "CTAS", "WDAY", "MELI", "CRWD", "PCAR", "MNST", "MCHP", "ADSK", "KDP", "LULU", "PAYX", "ROST", "IDXX", "AEP", "CPRT", "ODFL", "FAST", "GEHC", "DDOG", "MRVL", "DXCM", "BKR", "TEAM", "VRSK", "EXC", "CSX"]
    kospi = ["005930", "000660", "373220", "207940", "005380", "005490", "000270", "035420", "051910", "006400", "035720", "068270", "105560", "055550", "012330", "028260", "003550", "011200", "04370", "015760", "034730", "000810", "086790", "018261", "010950", "003670", "009150", "032830", "003490", "016360", "000720", "017670", "010130", "005935", "090430", "323410", "047050", "259960", "004020", "241560", "011170", "024110", "078930", "008770", "009540", "008930", "030200", "012450", "039490", "011070", "000060", "010620", "001450", "007070", "004800", "005830", "000990", "006360", "005070", "021240", "000210", "052690", "020150", "000100", "069500", "114800", "252670", "122630", "251340", "102110", "139260", "252710", "039130", "014680", "001040", "004170", "003240", "009830", "006800", "000150"]
    kosdaq = ["247540", "086520", "091990", "066970", "293490", "112040", "263750", "035760", "253450", "058470", "078600", "036570", "145020", "067160", "034230", "041510", "036830", "039200", "022100", "084370", "196170", "068760", "056190", "060250", "082270", "025900", "131370", "178920", "064550", "278280", "214150", "032500", "046890", "092190", "053800", "086900", "033640", "040300", "028300", "065650", "038500", "060720", "054780", "063170", "036200", "121600", "095700", "108320", "014200", "141080", "051370", "032620", "200130", "042000", "065150", "011370", "046120", "064260", "392560", "272210", "287410", "214310", "096530", "290670", "357780", "192820", "403420", "383800", "235980", "137400", "101160", "318020", "085660", "267250", "365340", "104200", "054540", "023160", "215600", "048260"]
    return sp500 if market_name == "S&P 500" else (nasdaq if market_name == "NASDAQ" else (kospi if market_name == "KOSPI" else kosdaq))

@st.cache_data
def get_master_name_map():
    m_map = {}
    m_map["NVDA"]="엔비디아"; m_map["AAPL"]="애플"; m_map["MSFT"]="마이크로소프트"; m_map["AMZN"]="아마존"; m_map["GOOGL"]="알파벳"; m_map["TSLA"]="테슬라"; m_map["META"]="메타"; m_map["AMD"]="AMD"; m_map["INTC"]="인텔"; m_map["NFLX"]="넷플릭스"
    m_map["QQQ"]="Invesco QQQ (나스닥100 ETF)"; m_map["TQQQ"]="ProShares 나스닥 3배 레버리지 ETF"; m_map["SQQQ"]="ProShares 나스닥 3배 인버스 ETF"; m_map["AVGO"]="브로드컴"; m_map["COST"]="코스트코"; m_map["PEP"]="펩시코"
    m_map["005930"]="삼성전자"; m_map["000660"]="SK하이닉스"; m_map["373220"]="LG에너지솔루션"; m_map["207940"]="삼성바이오로직스"; m_map["005380"]="현대차"; m_map["005490"]="POSCO홀딩스"; m_map["000270"]="기아"; m_map["035420"]="NAVER"
    m_map["069500"]="KODEX 200 (코스피 지수 ETF)"; m_map["114800"]="KODEX 인버스"; m_map["252670"]="KODEX 200선물인버스2X"; m_map["122630"]="KODEX 레버리지"; m_map["251340"]="KODEX 코스닥150인버스"
    return m_map

# ----------------------------------------------------------------------
# [팩트 기반 연산] 거래량 증감률 및 주가 평균 데이터 파싱 엔진
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_enhanced_market_data(market_name, start_date):
    tickers = get_ticker_pool(market_name)
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    
    # 금주(조회주차) 5일 정보 / 전주 5일 정보 산출
    this_start = start_date
    this_end = (st_dt + timedelta(days=4)).strftime("%Y-%m-%d")
    prev_start = (st_dt - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end = (st_dt - timedelta(days=3)).strftime("%Y-%m-%d")
    
    name_map = get_master_name_map()
    
    try:
        formatted_tickers = []
        for t in tickers:
            if market_name == "KOSPI": formatted_tickers.append(f"{t}.KS")
            elif market_name == "KOSDAQ": formatted_tickers.append(f"{t}.KQ")
            else: formatted_tickers.append(t)
            
        df = yf.download(" ".join(formatted_tickers), start=prev_start, end=this_end, group_by='ticker', progress=False)
        
        data_list = []
        for t in tickers:
            lookup_key = f"{t}.KS" if market_name == "KOSPI" else (f"{t}.KQ" if market_name == "KOSDAQ" else t)
            
            if lookup_key in df.columns.levels[0]:
                t_df = df[lookup_key].dropna()
                if not t_df.empty and len(t_df) >= 4:
                    # 1. 주간 누적 거래량 연산
                    this_week_vol = float(t_df['Volume'].loc[this_start:this_end].sum())
                    prev_week_vol = float(t_df['Volume'].loc[prev_start:prev_end].sum())
                    
                    if pd.isna(this_week_vol) or this_week_vol == 0: continue
                    if pd.isna(prev_week_vol) or prev_week_vol == 0: prev_week_vol = 1.0
                    
                    vol_change = ((this_week_vol - prev_week_vol) / prev_week_vol) * 100
                    
                    # 2. [요구사항 반영] 주가 변동성 파악을 위한 전주 vs 금주 주가 평균값 추출
                    this_price_avg = float(t_df['Close'].loc[this_start:this_end].mean())
                    prev_price_avg = float(t_df['Close'].loc[prev_start:prev_end].mean())
                    
                    name = name_map.get(t, f"일반 주식 ({t})")
                    
                    data_list.append({
                        "기업명(ETF명)": name, "티커": t,
                        "전주 평균주가": prev_price_avg, "금주 평균주가": this_price_avg,
                        "금주 누적거래량": this_week_vol, "거래량 증감률(%)": round(vol_change, 2)
                    })
        return pd.DataFrame(data_list)
    except:
        return pd.DataFrame()

# ----------------------------------------------------------------------
# 강조 가독성 스틸링 규칙 (튀는 종목 컬러링 함수)
# ----------------------------------------------------------------------
def highlight_interest(row):
    """기준점을 설정하여 튀는 종목에 색상 페인팅"""
    val = row["거래량 증감률(%)"]
    color = ''
    if val >= 50.0:
        color = 'background-color: #d4edda; color: #155724; font-weight: bold;'  # 관심 대폭발 (진녹색)
    elif val <= -30.0:
        color = 'background-color: #f8d7da; color: #721c24; font-weight: bold;'  # 관심 급감 / 탈출 신호 (연빨강)
    return [color] * len(row)

# ----------------------------------------------------------------------
# 인터페이스 출력 레이아웃
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        df_raw = get_enhanced_market_data(m_name, selected_dates["start"])
        
        if df_raw.empty:
            st.error("데이터 연산 점검 기간입니다. 다른 주차를 지정해 주세요.")
        else:
            # [요구사항 1] 상단에 기간과 함께 전주 대비 평균 증감률 명시
            market_avg_change = df_raw["거래량 증감률(%)"].mean()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="📅 분석 기간", value=selected_dates["label_period"])
            with col2:
                st.metric(label="📈 시장 전체 주간 평균 거래량 증감률", value=f"{market_avg_change:+.2f}%")
            
            # 필터 기능 작동
            if exclude_decreased:
                df_raw = df_raw[df_raw["거래량 증감률(%)"] >= 0]
                
            # 정렬 후 Top 50 컷 및 순위 배정
            df_top50 = df_raw.sort_values(by="금주 누적거래량", ascending=False).head(50).reset_index(drop=True)
            df_top50.index = (df_top50.index + 1).astype(str) + "위"
            df_top50.index.name = "순위"
            df_top50 = df_top50.reset_index()
            
            # [요구사항 3] 관심도 직관 차트 (돈이 몰리는 곳 vs 빠지는 곳 세부화)
            st.markdown("---")
            st.subheader("💡 거래량 데이터 시각적 판독기")
            
            g_col1, g_col2 = st.columns(2)
            with g_col1:
                st.success("🔥 이번 주 관심 폭발 (거래량 증가 상위 5)")
                df_burst = df_raw.sort_values(by="거래량 증감률(%)", ascending=False).head(5)
                st.bar_chart(data=df_burst, x="기업명(ETF명)", y="거래량 증감률(%)", color="#00CC96", use_container_width=True)
            with g_col2:
                st.error("❄️ 이번 주 관심 소멸 (거래량 급감 상위 5 ➡️ 나도 빠질 타이밍)")
                df_freeze = df_raw.sort_values(by="거래량 증감률(%)", ascending=True).head(5)
                st.bar_chart(data=df_freeze, x="기업명(ETF명)", y="거래량 증감률(%)", color="#FF4B4B", use_container_width=True)

            st.markdown("---")
            st.subheader(f"📊 {m_name} 주간 거래량 상위 Top 50 세부 지표")
            st.info("💡 팁: 거래량 증감률이 +50% 이상이면 초록색(관심 폭발), -30% 이하로 급감하면 빨간색(관심 소멸)으로 강조됩니다.")
            
            # [요구사항 2] 데이터 표 포맷팅 출력 및 색상 매핑 연동
            st.dataframe(
                df_top50.style.format({
                    "전주 평균주가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "금주 평균주가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "금주 누적거래량": "{:,.0f}",
                    "거래량 증감률(%)": "{:+.2f}%"
                }).apply(highlight_interest, axis=1),
                use_container_width=True,
                height=450,
                hide_index=True
            )
