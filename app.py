import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ----------------------------------------------------------------------
# 1. 페이지 레이아웃 및 텍스트 설정
# ----------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Market Volume Divergence Analyzer")
st.title("🎯 거래량-주가 괴리 판독 대시보드 (풀마켓 스캐너)")
st.caption("관심도(거래량) 폭발 및 소멸 종목을 발라내어 주식의 진입과 탈출 타이밍을 결정하는 팩트 시트")

# ----------------------------------------------------------------------
# 2. 제어판 (날짜 바인딩 및 스캔 설정)
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

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 스캔 범위 설정")
# API 과부하 방지를 위해 분석할 종목 수 제한 설정
scan_limit = st.sidebar.slider(
    "📊 분석할 시가총액 상위 종목 수", 
    min_value=50, max_value=500, value=150, step=50,
    help="조회 수가 높을수록 로딩 시간이 10~30초 길어질 수 있습니다."
)
exclude_decreased = st.sidebar.checkbox("📉 주간 거래량 감소 종목 필터링 (제외)", value=False)

# ----------------------------------------------------------------------
# 3. 마스터 자산 정보 데이터베이스 (동적 수집 + 한글 매핑)
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400) # 하루 한 번만 상장 리스트 갱신
def get_dynamic_ticker_pool(market_name, limit):
    """거래소별 실제 상장 종목을 실시간으로 가져옵니다."""
    dynamic_names = {}
    
    if market_name == "KOSPI" or market_name == "KOSDAQ":
        # 한국 시장은 FDR이 시가총액 순으로 정렬하여 제공함
        df = fdr.StockListing(market_name).head(limit)
        tickers = df['Code'].tolist()
        dynamic_names = dict(zip(df['Code'], df['Name']))
        
    elif market_name == "S&P 500":
        df = fdr.StockListing('S&P500').head(limit)
        tickers = df['Symbol'].tolist()
        dynamic_names = dict(zip(df['Symbol'], df['Name']))
        
    elif market_name == "NASDAQ":
        # 나스닥은 워낙 방대하여 기본 대표주 및 QQQ 구성종목 위주 하드코딩 리스트를 확장하여 사용
        # (무료 API 한계상 전체 풀 스캔 시 시간 초과 발생 우려)
        base_nasdaq = ["QQQ", "TQQQ", "SQQQ", "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "AVGO", "COST", "ASML", "AZN", "PEP", "LIN", "ADBE", "AMD", "CSCO", "TMUS", "CMCSA", "TXN", "QCOM", "AMAT", "ISRG", "HON", "MU", "INTU", "BKNG", "AMGN", "LRCX", "ADI", "PANW", "MDLZ", "REGN", "PDD", "VRTX", "KLAC", "SNPS", "CDNS", "CHTR", "MAR", "ORLY", "NXPI", "CTAS", "WDAY", "MELI", "CRWD", "PCAR", "MNST", "MCHP", "ADSK", "KDP", "LULU", "PAYX", "ROST", "IDXX", "AEP", "CPRT", "ODFL", "FAST", "GEHC", "DDOG", "MRVL", "DXCM", "BKR", "TEAM", "VRSK", "EXC", "CSX"]
        df = fdr.StockListing('NASDAQ')
        extra_tickers = df['Symbol'].head(limit).tolist()
        tickers = list(set(base_nasdaq + extra_tickers))[:limit]
        dynamic_names = dict(zip(df['Symbol'], df['Name']))
        
    return tickers, dynamic_names

def get_master_name_map():
    """핵심 기술주 및 ETF용 직관적 한글명 강제 덮어쓰기 딕셔너리"""
    m_map = {
        "NVDA":"엔비디아", "AAPL":"애플", "MSFT":"마이크로소프트", "AMZN":"아마존", "GOOGL":"알파벳", 
        "TSLA":"테슬라", "META":"메타", "AMD":"AMD", "INTC":"인텔", "NFLX":"넷플릭스", "AVGO":"브로드컴", 
        "QQQ":"Invesco QQQ (나스닥100)", "TQQQ":"ProShares 나스닥 3배 레버리지", "SQQQ":"ProShares 나스닥 3배 인버스",
        "SPY":"SPDR S&P 500", "SOXL":"Direxion 반도체 3배 레버리지", "SOXS":"Direxion 반도체 3배 인버스",
        "005930":"삼성전자", "000660":"SK하이닉스", "373220":"LG에너지솔루션", "207940":"삼성바이오로직스", 
        "069500":"KODEX 200", "114800":"KODEX 인버스", "252670":"KODEX 200선물인버스2X", "122630":"KODEX 레버리지"
    }
    return m_map

def get_etf_description(ticker):
    etf_map = {
        "QQQ": "나스닥 100 지수를 1배로 추종하는 미국 대표 기술주 ETF",
        "TQQQ": "나스닥 100 일일 변동성의 3배를 추종하는 고위험 레버리지",
        "SPY": "미국 시장 전체를 대변하는 S&P 500 지수 추종 ETF",
        "069500": "KODEX 200: 코스피 우량기업 200개 종목 지수 추종"
    }
    return etf_map.get(ticker, "섹터 주도 개별 기업 (또는 동적 스캔 종목)")

# ----------------------------------------------------------------------
# 4. 데이터 로드 및 팩트 수집 코어 엔진
# ----------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_enhanced_market_data(market_name, start_date, end_date, limit):
    tickers, dynamic_names = get_dynamic_ticker_pool(market_name, limit)
    hardcoded_names = get_master_name_map()
    
    st_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prev_start = (st_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    prev_end = (st_dt - timedelta(days=3)).strftime("%Y-%m-%d")
    
    data_list = []
    
    try:
        # 한국 시장 (FinanceDataReader 개별 순회)
        if market_name in ["KOSPI", "KOSDAQ"]:
            for t in tickers:
                # 하드코딩된 한글명 우선 -> 없으면 동적 수집된 한글명 -> 없으면 티커
                name = hardcoded_names.get(t, dynamic_names.get(t, t))
                hist = fdr.DataReader(t, prev_start, end_date)
                
                if not hist.empty and len(hist) >= 4:
                    this_vol = float(hist['Volume'].loc[start_date:end_date].sum())
                    prev_vol = float(hist['Volume'].loc[prev_start:prev_end].sum())
                    if pd.isna(this_vol) or this_vol == 0: continue
                    vol_change = ((this_vol - prev_vol) / (prev_vol if prev_vol > 0 else 1.0)) * 100
                    
                    this_price = float(hist['Close'].loc[start_date:end_date].mean())
                    prev_price = float(hist['Close'].loc[prev_start:prev_end].mean())
                    price_change = ((this_price - prev_price) / (prev_price if prev_price > 0 else 1.0)) * 100
                    
                    data_list.append({
                        "기업명": name, "티커": t,
                        "전주 평균주가": prev_price, "금주 평균주가": this_price, "주가 증감률(%)": round(price_change, 2),
                        "금주 누적거래량": this_vol, "거래량 증감률(%)": round(vol_change, 2)
                    })
            return pd.DataFrame(data_list)
        
        # 미국 시장 (yfinance 대량 병렬 다운로드)
        else:
            df = yf.download(" ".join(tickers), start=prev_start, end=end_date, group_by='ticker', progress=False)
            for t in tickers:
                # 하드코딩된 한글명 우선 -> 없으면 영어 공식명 -> 없으면 티커
                name = hardcoded_names.get(t, dynamic_names.get(t, t))
                
                # 티커 1개일 때와 여러 개일 때 yfinance 반환 구조가 다름을 방어
                if len(tickers) == 1:
                    t_df = df.dropna()
                else:
                    if t in df.columns.levels[0]:
                        t_df = df[t].dropna()
                    else:
                        continue
                        
                if not t_df.empty and len(t_df) >= 4:
                    this_vol = float(t_df['Volume'].loc[start_date:end_date].sum())
                    prev_vol = float(t_df['Volume'].loc[prev_start:prev_end].sum())
                    if pd.isna(this_vol) or this_vol == 0: continue
                    vol_change = ((this_vol - prev_vol) / (prev_vol if prev_vol > 0 else 1.0)) * 100
                    
                    this_price = float(t_df['Close'].loc[start_date:end_date].mean())
                    prev_price = float(t_df['Close'].loc[prev_start:prev_end].mean())
                    price_change = ((this_price - prev_price) / (prev_price if prev_price > 0 else 1.0)) * 100
                    
                    data_list.append({
                        "기업명": name, "티커": t,
                        "전주 평균주가": prev_price, "금주 평균주가": this_price, "주가 증감률(%)": round(price_change, 2),
                        "금주 누적거래량": this_vol, "거래량 증감률(%)": round(vol_change, 2)
                    })
            return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"데이터 로드 중 에러 발생: {e}")
        return pd.DataFrame()

# 데이터 테이블 하이라이팅 (컬러 매핑)
def highlight_rows(row):
    val = row["거래량 증감률(%)"]
    if val >= 50.0: return ['background-color: #d4edda; color: #155724; font-weight: bold;'] * len(row)
    elif val <= -30.0: return ['background-color: #f8d7da; color: #721c24; font-weight: bold;'] * len(row)
    return [''] * len(row)

# ----------------------------------------------------------------------
# 5. 4대 지수 화면 렌더링 (Plotly 복합 차트 연동)
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        with st.spinner(f"📡 {m_name} 시장의 상위 {scan_limit}개 종목 데이터를 실시간으로 수집하고 분석 중입니다..."):
            df_raw = get_enhanced_market_data(m_name, selected_dates["start"], selected_dates["end"], scan_limit)
        
        if df_raw.empty:
            st.warning("선택하신 기간의 데이터가 부족하거나, 현재 시장이 닫혀있습니다.")
        else:
            market_avg_change = df_raw["거래량 증감률(%)"].mean()
            
            # 상단 대시보드 요약
            col1, col2 = st.columns(2)
            with col1: st.metric(label="📅 분석 기간 주차", value=selected_dates["label_period"])
            with col2: st.metric(label="📈 시장 전체 주간 평균 거래량 증감률", value=f"{market_avg_change:+.2f}%")
            
            if exclude_decreased:
                df_raw = df_raw[df_raw["거래량 증감률(%)"] >= 0]
                
            # 정렬 후 Top N 컷팅 및 '순위' 배정 (거래량 급증 종목 우선)
            df_top = df_raw.sort_values(by="거래량 증감률(%)", ascending=False).head(50).reset_index(drop=True)
            df_top.index = (df_top.index + 1).astype(str) + "위"
            df_top.index.name = "순위"
            df_top = df_top.reset_index()
            
            # 마우스 오버용 ETF/종목 툴팁 매핑
            df_top["종목 설명"] = df_top["티커"].apply(get_etf_description)
            
            # ----------------------------------------------------------------------
            # [의도 완벽 반영] 거래량 vs 주가 다이버전스 복합 차트 (Plotly)
            # ----------------------------------------------------------------------
            st.markdown("---")
            st.subheader(f"📈 {m_name} 다이버전스 판독 차트 (거래량 급증 Top 10)")
            st.caption("💡 차트에 마우스를 올리면 **[기업명, 티커, 거래량 증감, 주가 증감률]** 팩트가 한눈에 나타납니다. 거래량은 급감하는데 주가는 버티고 있다면 **탈출(익절)**을 고려하세요.")
            
            df_chart = df_top.head(10).copy()
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # 1. 거래량 막대그래프 (좌측 축)
            fig.add_trace(
                go.Bar(
                    x=df_chart["기업명"], 
                    y=df_chart["거래량 증감률(%)"], 
                    name="주간 거래량 증감률",
                    marker_color="#1f77b4",
                    customdata=df_chart[["티커", "금주 누적거래량"]],
                    hovertemplate="<b>%{x} (%{customdata[0]})</b><br>전주대비 거래량: %{y:+.2f}%<br>누적거래량: %{customdata[1]:,.0f}주<extra></extra>"
                ),
                secondary_y=False,
            )
            
            # 2. 주가 증감률 선그래프 (우측 축)
            fig.add_trace(
                go.Scatter(
                    x=df_chart["기업명"], 
                    y=df_chart["주가 증감률(%)"], 
                    name="주가 증감률(%)",
                    mode="lines+markers",
                    line=dict(color="#ff7f0e", width=4),
                    marker=dict(size=8),
                    hovertemplate="<b>%{x}</b><br>주가 증감률: %{y:+.2f}%<extra></extra>"
                ),
                secondary_y=True,
            )
            
            fig.update_layout(
                autosize=True, height=500, margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified"
            )
            fig.update_yaxes(title_text="주간 거래량 증감률 (%)", secondary_y=False, showgrid=False)
            fig.update_yaxes(title_text="주가 증감률 (%)", secondary_y=True, showgrid=True)
            
            st.plotly_chart(fig, use_container_width=True)

            # ----------------------------------------------------------------------
            # 팩트 시트 데이터 테이블
            # ----------------------------------------------------------------------
            st.markdown("---")
            st.subheader(f"📊 {m_name} 거래/주가 상세 지표 (Top 50)")
            st.info("🔥 녹색 배경: 거래량 50% 이상 급증 (돈 쏠림)  |  ❄️ 빨간색 배경: 거래량 30% 이상 급감 (돈 이탈 / 탈출 신호)")
            
            df_styled = df_top[["순위", "기업명", "티커", "전주 평균주가", "금주 평균주가", "주가 증감률(%)", "금주 누적거래량", "거래량 증감률(%)", "종목 설명"]]
            
            st.dataframe(
                df_styled.style.format({
                    "전주 평균주가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "금주 평균주가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "주가 증감률(%)": "{:+.2f}%",
                    "금주 누적거래량": "{:,.0f}",
                    "거래량 증감률(%)": "{:+.2f}%"
                }).apply(highlight_rows, axis=1),
                use_container_width=True,
                height=600,
                hide_index=True
            )
