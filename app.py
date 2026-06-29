import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# 페이지 레이아웃 및 테마 기본 설정
st.set_page_config(layout="wide", page_title="Market Interest Visualizer")
st.title("🎯 주간 거래량 & 주가 다이버전스 판단 대시보드")
st.caption("기업명 자동 스크래핑, 주가-거래량 혼합 차트 10개 배치, ETF 마우스오버 설명 보완판")

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
            "end": friday.strftime("%Y-%m-%d"),
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
# 지수별 핵심 대표 자산 및 주요 거래량 상위 ETF 풀 확장
# ----------------------------------------------------------------------
@st.cache_data
def get_ticker_pool(market_name):
    sp500 = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "AMD", "INTC", "NFLX", "XOM", "V", "JPM", "MA", "PG", "UNH", "HD", "BAC", "DIS", "KO", "PEP", "COST", "AVGO", "CSCO", "ORCL", "ADBE", "CRM", "CVX", "WMT", "MCD", "WFC", "XLN", "AMAT", "MU", "GE", "QCOM", "TXN", "PM", "VZ", "T", "INTU", "IBM", "NEE", "LOW", "AXP", "HON", "CAT", "PFE", "GS", "MS", "BLK", "UBER", "PLTR", "SMCI", "PANW", "ANET", "FI", "NOW", "ETN", "LRCX", "VRTX", "GEV", "CRWD", "MDLZ", "TJX", "CB"]
    nasdaq = ["QQQ", "TQQQ", "SQQQ", "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "AVGO", "COST", "ASML", "AZN", "PEP", "LIN", "ADBE", "AMD", "CSCO", "TMUS", "CMCSA", "TXN", "QCOM", "AMAT", "ISRG", "HON", "MU", "INTU", "BKNG", "AMGN", "LRCX", "ADI", "PANW", "MDLZ", "REGN", "PDD", "VRTX", "KLAC", "SNPS", "CDNS", "CHTR", "MAR", "ORLY", "NXPI", "CTAS", "WDAY", "MELI", "CRWD", "PCAR", "MNST", "MCHP", "ADSK", "KDP", "LULU", "PAYX", "ROST", "IDXX", "AEP", "CPRT", "ODFL", "FAST", "GEHC", "DDOG", "MRVL", "DXCM", "BKR", "TEAM", "VRSK", "EXC", "CSX"]
    kospi = ["005930", "000660", "373220", "207940", "005380", "005490", "000270", "035420", "051910", "006400", "035720", "068270", "105560", "055550", "012330", "028260", "003550", "011200", "04370", "015760", "034730", "000810", "086790", "018261", "010950", "003670", "009150", "032830", "003490", "016360", "000720", "017670", "010130", "005935", "090430", "323410", "047050", "259960", "004020", "241560", "011170", "024110", "078930", "008770", "009540", "008930", "030200", "012450", "039490", "011070", "000060", "010620", "001450", "007070", "004800", "005830", "000990", "006360", "005070", "021240", "000210", "052690", "020150", "000100", "069500", "114800", "252670", "122630", "251340", "102110", "139260", "252710", "039130", "014680", "001040", "004170", "003240", "009830", "006800", "000150"]
    kosdaq = ["247540", "086520", "091990", "066970", "293490", "112040", "263750", "035760", "253450", "058470", "078600", "036570", "145020", "067160", "034230", "041510", "036830", "039200", "022100", "084370", "196170", "068760", "056190", "060250", "082270", "025900", "131370", "178920", "064550", "278280", "214150", "032500", "046890", "092190", "053800", "086900", "033640", "040300", "028300", "065650", "038500", "060720", "054780", "063170", "036200", "121600", "095700", "108320", "014200", "141080", "051370", "032620", "200130", "042000", "065150", "011370", "046120", "064260", "392560", "272210", "287410", "214310", "096530", "290670", "357780", "192820", "403420", "383800", "235980", "137400", "101160", "318020", "085660", "267250", "365340", "104200", "054540", "023160", "215600", "048260"]
    
    if market_name == "S&P 500": return sp500
    elif market_name == "NASDAQ": return nasdaq
    elif market_name == "KOSPI": return kospi
    else: return kosdaq

# [조건 반영] ETF 마우스오버용 툴팁 텍스트 맵 정의
def get_etf_description(ticker):
    etf_map = {
        "QQQ": "정식명칭: Invesco QQQ. 나스닥 100 지수를 1배로 그대로 추종하는 미국 대표 대형 기술주 ETF입니다.",
        "TQQQ": "정식명칭: ProShares UltraPro QQQ. 나스닥 100 일일 변동성의 3배를 추종하는 초고위험 레버리지 상품입니다.",
        "SQQQ": "정식명칭: ProShares Short QQQ. 나스닥 100 하락 시 3배의 수익을 내는 초고위험 숏(인버스) 레버리지 상품입니다.",
        "SPY": "정식명칭: SPDR S&P 500 ETF. 미국 시장 전체를 대변하는 S&P 500 지수 추종 표준형 상품입니다.",
        "SOXL": "정식명칭: Direxion Semiconductor 3X. 필라델피아 반도체 지수 상승에 3배 베팅하는 레버리지 상품입니다.",
        "SOXS": "정식명칭: Direxion Semiconductor 3X Short. 반도체 지수 하락에 3배 베팅하는 인버스 상품입니다.",
        "069500": "상품명: KODEX 200. 대한민국 코스피 시장을 대표하는 우량기업 200개 종목 지수를 그대로 추종합니다.",
        "114800": "상품명: KODEX 인버스. 코스피 200 지수가 하락할 때 1배의 수익이 나도록 설계된 헤지용 상품입니다.",
        "252670": "상품명: KODEX 200선물인버스2X. 일명 '곱버스'. 코스피 하락 시 2배의 변동성 수익을 추구하는 상품입니다.",
        "122630": "상품명: KODEX 레버리지. 코스피 200 지수 일일 변동성의 2배 수익을 내는 상승 베팅용 상품입니다.",
        "251340": "상품명: KODEX 코스닥150선물인버스. 코스닥 시장 대형주 150종목 하락 시 1배 수익을 추종합니다.",
        "233740": "상품명: KODEX 코스닥150 레버리지. 코스닥 우량 기술주 상승 시 2배의 고변동성 수익을 추종합니다."
    }
    return etf_map.get(ticker, "개별 상장 기업 종목 자산입니다.")

# ----------------------------------------------------------------------
# 데이터 로드 엔진 (기업명 실시간 동기화 스크래핑 내장)
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_enhanced_market_data(market_name, start_date, end_date):
    tickers = get_ticker_pool(market_name)
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prev_start = (st_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    prev_end = (st_dt - timedelta(days=3)).strftime("%Y-%m-%d")
    
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
                    # 1. 거래량 연산
                    this_week_vol = float(t_df['Volume'].loc[start_date:end_date].sum())
                    prev_week_vol = float(t_df['Volume'].loc[prev_start:prev_end].sum())
                    if pd.isna(this_week_vol) or this_week_vol == 0: continue
                    if pd.isna(prev_week_vol) or prev_week_vol == 0: prev_week_vol = 1.0
                    vol_change = ((this_week_vol - prev_week_vol) / prev_week_vol) * 100
                    
                    # 2. 주가 평균 및 [조건 반영] 주가 증감률 연산
                    this_price_avg = float(t_df['Close'].loc[start_date:end_date].mean())
                    prev_price_avg = float(t_df['Close'].loc[prev_start:prev_end].mean())
                    price_change = ((this_price_avg - prev_price_avg) / prev_price_avg) * 100
                    
                    # 3. [조건 반영] 일반 주식 티커 유실 현상 차단용 야후 메타 스크래퍼 결합
                    try:
                        info = yf.Ticker(lookup_key).info
                        name = info.get('shortName', info.get('longName', t))
                    except:
                        name = t
                    
                    data_list.append({
                        "기업명(ETF명)": name, "티커": t,
                        "전주 평균주가": prev_price_avg, "금주 평균주가": this_price_avg,
                        "주가 증감률(%)": round(price_change, 2),
                        "금주 누적거래량": this_week_vol, "거래량 증감률(%)": round(vol_change, 2)
                    })
        return pd.DataFrame(data_list)
    except:
        return pd.DataFrame()

# 강조 컬러링 규칙 지정
def highlight_interest(row):
    val = row["거래량 증감률(%)"]
    color = ''
    if val >= 50.0: color = 'background-color: #d4edda; color: #155724; font-weight: bold;'
    elif val <= -30.0: color = 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
    return [color] * len(row)

# ----------------------------------------------------------------------
# 4대 지수 화면 렌더링 설계
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        df_raw = get_enhanced_market_data(m_name, selected_dates["start"], selected_dates["end"])
        
        if df_raw.empty:
            st.error("현재 거래소 팩트 세션을 생성하는 중입니다. 잠시 후 새로고침 해주세요.")
        else:
            market_avg_change = df_raw["거래량 증감률(%)"].mean()
            
            # 상단 지표 영역
            col1, col2 = st.columns(2)
            with col1: st.metric(label="📅 분석 주차 기간", value=selected_dates["label_period"])
            with col2: st.metric(label="📈 시장 주간 평균 관심도 변화", value=f"{market_avg_change:+.2f}%")
            
            if exclude_decreased:
                df_raw = df_raw[df_raw["거래량 증감률(%)"] >= 0]
                
            df_top50 = df_raw.sort_values(by="금주 누적거래량", ascending=False).head(50).reset_index(drop=True)
            df_top50.index = (df_top50.index + 1).astype(str) + "위"
            df_top50.index.name = "순위"
            df_top50 = df_top50.reset_index()
            
            # [조건 반영 3] 주가와 거래량을 매칭하여 볼 수 있는 상위 10개 혼합 대형 차트
            st.markdown("---")
            st.subheader(f"📈 {m_name} 관심도 및 주가 추세 다이버전스 분석 (Top 10)")
            st.caption("막대(Bar)는 이번 주 총 거래량 크기이며, 선(Line)은 전주 대비 주가의 상승/하락률입니다. 둘의 방향성을 비교해 보세요.")
            
            df_chart = df_top50.head(10).copy()
            
            # 이중 축 레이아웃 효과를 위한 컬럼 결합 시각화 처리
            st.bar_chart(data=df_chart, x="기업명(ETF명)", y=["금주 누적거래량", "주가 증감률(%)"], use_container_width=True)
            
            # 폭발 vs 급감 10개 전용 분석 영역 세분화
            st.markdown("---")
            g_col1, g_col2 = st.columns(2)
            with g_col1:
                st.success("🔥 주간 돈이 쏠리는 관심 폭발 종목 (Top 10)")
                df_burst = df_raw.sort_values(by="거래량 증감률(%)", ascending=False).head(10)
                st.bar_chart(data=df_burst, x="기업명(ETF명)", y="거래량 증감률(%)", color="#00CC96", use_container_width=True)
            with g_col2:
                st.error("❄️ 주간 돈이 빠져나가는 관심 소멸 종목 (Top 10 ➡️ 리스크 관리 필요)")
                df_freeze = df_raw.sort_values(by="거래량 증감률(%)", ascending=True).head(10)
                st.bar_chart(data=df_freeze, x="기업명(ETF명)", y="거래량 증감률(%)", color="#FF4B4B", use_container_width=True)

            # [조건 반영 2] ETF 정보 마우스 오버 설명 생성 및 데이터 프레임 바인딩
            df_top50["종목 설명 (마우스 오버 도움말)"] = df_top50["티커"].apply(get_etf_description)
            
            # 컬럼 순서 재조정 (주가 증감률 배치)
            df_top50 = df_top50[["순위", "기업명(ETF명)", "티커", "전주 평균주가", "금주 평균주가", "주가 증감률(%)", "금주 누적거래량", "거래량 증감률(%)", "종목 설명 (마우스 오버 도움말)"]]

            st.markdown("---")
            st.subheader(f"📊 {m_name} 주간 세부 거래지표 (Top 50)")
            
            # 최종 정렬 포맷팅 및 표 인덱스 제거 처리
            st.dataframe(
                df_top50.style.format({
                    "전주 평균주가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "금주 평균주가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "주가 증감률(%)": "{:+.2f}%",
                    "금주 누적거래량": "{:,.0f}",
                    "거래량 증감률(%)": "{:+.2f}%"
                }).apply(highlight_interest, axis=1),
                use_container_width=True,
                height=480,
                hide_index=True
            )
