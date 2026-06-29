import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import plotly.graph_objects as  from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# 페이지 전체 레이아웃 설정
st.set_page_config(layout="wide", page_title="Market Volume Divergence Analyzer")
st.title("🎯 거래량-주가 괴리 판독 최종 대시보드")
st.caption("관심도(거래량) 폭발 및 소멸 종목을 발라내어 주식의 진입과 탈출 타이밍을 결정하는 팩트 시트")

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
            "label_period": f"{monday.strftime('%Y-%m-%d')} ~ {friday.strftime('%m.%d')}"
        }
    return options

weekly_options = get_cached_weeks()

# 사이드바 제어판
st.sidebar.header("🔧 대시보드 제어판")
selected_week_label = st.sidebar.selectbox("🔍 조회 주차 선택", list(weekly_options.keys()))
selected_dates = weekly_options[selected_week_label]
exclude_decreased = st.sidebar.checkbox("📉 주간 거래량 감소 종목 필터링 (제외)", value=False)

# ----------------------------------------------------------------------
# 마스터 자산 정보 데이터베이스 세팅 (100% 한글명 처리)
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
    # 미국 시장 및 대표 지수형 ETF 마스터 매핑
    m_map["NVDA"]="엔비디아"; m_map["AAPL"]="애플"; m_map["MSFT"]="마이크로소프트"; m_map["AMZN"]="아마존"; m_map["GOOGL"]="알파벳"; m_map["TSLA"]="테슬라"; m_map["META"]="메타"; m_map["AMD"]="AMD"; m_map["INTC"]="인텔"; m_map["NFLX"]="넷플릭스"; m_map["AVGO"]="브로드컴"; m_map["COST"]="코스트코"; m_map["PEP"]="펩시코"
    m_map["QQQ"]="Invesco QQQ (나스닥100 추종)"; m_map["TQQQ"]="ProShares 나스닥 3배 레버리지"; m_map["SQQQ"]="ProShares 나스닥 3배 인버스"
    m_map["SPY"]="SPDR S&P 500 지수 추종"; m_map["SOXL"]="Direxion 반도체 3배 레버리지"; m_map["SOXS"]="Direxion 반도체 3배 인버스"
    # 한국 시장 및 대표 ETF 마스터 매핑
    m_map["005930"]="삼성전자"; m_map["000660"]="SK하이닉스"; m_map["373220"]="LG에너지솔루션"; m_map["207940"]="삼성바이오로직스"; m_map["005380"]="현대차"; m_map["005490"]="POSCO홀딩스"; m_map["000270"]="기아"; m_map["035420"]="NAVER"
    m_map["069500"]="KODEX 200 (코스피 지수형)"; m_map["114800"]="KODEX 인버스 헤지형"; m_map["252670"]="KODEX 200선물인버스2X (곱버스)"; m_map["122630"]="KODEX 레버리지 (상승2배)"; m_map["251340"]="KODEX 코스닥150인버스"
    return m_map

# ----------------------------------------------------------------------
# 데이터 로드 및 팩트 수집 코어 엔진
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_enhanced_market_data(market_name, start_date, end_date):
    tickers = get_ticker_pool(market_name)
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prev_start = (st_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    prev_end = (st_dt - timedelta(days=3)).strftime("%Y-%m-%d")
    name_map = get_master_name_map()
    
    try:
        if market_name in ["KOSPI", "KOSDAQ"]:
            df_listing = fdr.StockListing(market_name)
            data_list = []
            for _, row in df_listing.head(120).iterrows():
                t = row['Code']
                name = name_map.get(t, row['Name'])
                hist = fdr.DataReader(t, prev_start, end_date)
                if not hist.empty and len(hist) >= 5:
                    this_vol = float(hist['Volume'].loc[start_date:end_date].sum())
                    prev_vol = float(hist['Volume'].loc[prev_start:prev_end].sum())
                    if pd.isna(this_vol) or this_vol == 0: continue
                    vol_change = ((this_vol - prev_vol) / (prev_vol if prev_vol > 0 else 1.0)) * 100
                    
                    this_price = float(hist['Close'].loc[start_date:end_date].mean())
                    prev_price = float(hist['Close'].loc[prev_start:prev_end].mean())
                    price_change = ((this_price - prev_price) / (prev_price if prev_price > 0 else 1.0)) * 100
                    
                    data_list.append({
                        "기업명(ETF명)": name, "티커": t,
                        "주가 증감률(%)": round(price_change, 2),
                        "금주 누적거래량": this_vol, "거래량 증감률(%)": round(vol_change, 2)
                    })
            return pd.DataFrame(data_list)
        else:
            df = yf.download(" ".join(tickers), start=prev_start, end=end_date, group_by='ticker', progress=False)
            data_list = []
            for t in tickers:
                if t in df.columns.levels[0]:
                    t_df = df[t].dropna()
                    if not t_df.empty and len(t_df) >= 4:
                        this_vol = float(t_df['Volume'].loc[start_date:end_date].sum())
                        prev_vol = float(t_df['Volume'].loc[prev_start:prev_end].sum())
                        if pd.isna(this_vol) or this_vol == 0: continue
                        vol_change = ((this_vol - prev_vol) / (prev_vol if prev_vol > 0 else 1.0)) * 100
                        
                        this_price = float(t_df['Close'].loc[start_date:end_date].mean())
                        prev_price = float(t_df['Close'].loc[prev_start:prev_end].mean())
                        price_change = ((this_price - prev_price) / (prev_price if prev_price > 0 else 1.0)) * 100
                        
                        data_list.append({
                            "기업명(ETF명)": name_map.get(t, t), "티커": t,
                            "주가 증감률(%)": round(price_change, 2),
                            "금주 누적거래량": this_vol, "거래량 증감률(%)": round(vol_change, 2)
                        })
            return pd.DataFrame(data_list)
    except:
        return pd.DataFrame()

def highlight_rows(row):
    val = row["거래량 증감률(%)"]
    if val >= 50.0: return ['background-color: #d4edda; color: #155724; font-weight: bold;'] * len(row)
    elif val <= -30.0: return ['background-color: #f8d7da; color: #721c24; font-weight: bold;'] * len(row)
    return [''] * len(row)

# ----------------------------------------------------------------------
# 4대 지수 독립 화면 구성 및 복합 판단 인터페이스 출력
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        df_raw = get_enhanced_market_data(m_name, selected_dates["start"], selected_dates["end"])
        
        if df_raw.empty:
            st.error("거래소 원본 데이터를 동기화하는 중입니다. 잠시 후 새로고침 해주세요.")
        else:
            market_avg_change = df_raw["거래량 증감률(%)"].mean()
            
            # 상단 대시보드 스냅샷 요약 라인
            col1, col2 = st.columns(2)
            with col1: st.metric(label="📅 분석 기간 주차", value=selected_dates["label_period"])
            with col2: st.metric(label="📈 시장 전체 주간 평균 거래량 변화량", value=f"{market_avg_change:+.2f}%")
            
            if exclude_decreased:
                df_raw = df_raw[df_raw["거래량 증감률(%)"] >= 0]
                
            # 정렬 및 50위 커팅 후 '순위' 재정렬 완료
            df_top50 = df_raw.sort_values(by="금주 누적거래량", ascending=False).head(50).reset_index(drop=True)
            df_top50.index = (df_top50.index + 1).astype(str) + "위"
            df_top50.index.name = "순위"
            df_top50 = df_top50.reset_index()
            
            # [의도 반영] 주가와 거래량의 다이버전스를 완벽하게 보여주는 대형 결합 차트 구현
            st.markdown("---")
            st.subheader(f"📈 {m_name} 거래량 변동 및 주가 변동성 다이버전스 분석 (Top 10)")
            st.caption("💡 차트에 마우스를 올리면 기업명, 티커, 거래량 및 주가 증감률이 완전한 카드 형태로 팝업됩니다.")
            
            df_chart = df_top50.head(10)
            
            # Plotly를 이용한 이중 축(Dual-Axis) 복합 차트 드로잉 (기업명 매핑 완료)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # 거래량 막대그래프 배치
            fig.add_trace(
                go.Bar(
                    x=df_chart["기업명(ETF명)"], 
                    y=df_chart["금주 누적거래량"], 
                    name="금주 누적거래량",
                    marker_color="#1f77b4",
                    hovertemplate="<b>%{x}</b><br>누적거래량: %{y:,.0f}주<extra></extra>"
                ),
                secondary_y=False,
            )
            
            # 주가 증감률 선그래프 배치
            fig.add_trace(
                go.Scatter(
                    x=df_chart["기업명(ETF명)"], 
                    y=df_chart["주가 증감률(%)"], 
                    name="주가 증감률(%)",
                    mode="lines+markers+text",
                    line=dict(color="#ff7f0e", width=3),
                    text=df_chart["주가 증감률(%)"].map(lambda x: f"{x:+.1f}%"),
                    textposition="top center",
                    hovertemplate="<b>%{x}</b><br>주가 증감률: %{y:+.2f}%<extra></extra>"
                ),
                secondary_y=True,
            )
            
            fig.update_layout(
                autosize=True, height=500, margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified"
            )
            fig.update_xaxes(title_text="기업명 / 자산명")
            fig.update_yaxes(title_text="주간 거래량 (주)", secondary_y=False, showgrid=False)
            fig.update_yaxes(title_text="주가 증감률 (%)", secondary_y=True, showgrid=True)
            
            st.plotly_chart(fig, use_container_width=True)

            # 세부 수치 데이터프레임 매핑 출력 영역
            st.markdown("---")
            st.subheader(f"📊 {m_name} 주간 거래량 상위 Top 50 팩트 시트")
            st.info("🔥 녹색: 거래량 50% 이상 급증 (돈 쏠림)  |  ❄️ 빨간색: 거래량 30% 이상 급감 (돈 이탈 ➡️ 탈출 신호)")
            
            df_styled = df_top50[["순위", "기업명(ETF명)", "티커", "금주 누적거래량", "거래량 증감률(%)", "주가 증감률(%)"]]
            
            st.dataframe(
                df_styled.style.format({
                    "금주 누적거래량": "{:,.0f}",
                    "거래량 증감률(%)": "{:+.2f}%",
                    "주가 증감률(%)": "{:+.2f}%"
                }).apply(highlight_rows, axis=1),
                use_container_width=True,
                height=500,
                hide_index=True
            )
