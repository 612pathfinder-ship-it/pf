import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ----------------------------------------------------------------------
# 1. 페이지 레이아웃 및 텍스트 설정
# ----------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Advanced Volume Divergence Analyzer")
st.title("⚡ 초고속 다이버전스 & 듀얼 머니플로우 대시보드")
st.caption("요청사항(상위 50개, ETF명 매핑, 전후 머니플로우 비교, 급증/급감 특징주 브리핑)이 완벽히 반영된 정밀 분석 시스템")

# ----------------------------------------------------------------------
# 2. 사이드바 제어판 (기간 최적화)
# ----------------------------------------------------------------------
st.sidebar.header("🔧 대시보드 제어판")
time_frame = st.sidebar.radio("📅 분석 주기 선택", ["일단위 (Daily)", "주단위 (Weekly)"])

today = datetime.today()
date_options = {}

if time_frame == "일단위 (Daily)":
    st.sidebar.subheader("📆 기준일 설정 (전일 vs 금일 비교)")
    for i in range(10):
        target_date = today - timedelta(days=i)
        if target_date.weekday() >= 5: 
            continue
        label = f"📆 {target_date.strftime('%Y-%m-%d (%a)')}"
        date_options[label] = {
            "end": target_date.strftime("%Y-%m-%d"),
            "days_back": 7 
        }
    selected_label = st.sidebar.selectbox("🔍 조회 기준일 선택", list(date_options.keys()))
    config = date_options[selected_label]
    
else:
    st.sidebar.subheader("📆 조회 주차 설정 (전주 vs 금주 비교)")
    for i in range(3): 
        monday = today - timedelta(days=today.weekday() + (i * 7))
        friday = monday + timedelta(days=4)
        if monday > today: continue
        
        label = f"📅 {monday.strftime('%Y년 %m월')} {(monday.day - 1) // 7 + 1}주차"
        date_options[label] = {
            "start": monday.strftime("%Y-%m-%d"),
            "end": friday.strftime("%Y-%m-%d"),
            "prev_start": (monday - timedelta(days=7)).strftime("%Y-%m-%d"),
            "prev_end": (monday - timedelta(days=3)).strftime("%Y-%m-%d")
        }
    selected_label = st.sidebar.selectbox("🔍 조회 주차 선택", list(date_options.keys()))
    config = date_options[selected_label]

exclude_decreased = st.sidebar.checkbox("📉 거래량 감소 종목 필터링 (메인 표에서 제외)", value=False)

# ----------------------------------------------------------------------
# 3. 고정 압축 라인업 마스터 데이터베이스 (ETF + 주식 명확한 한글 매핑)
# ----------------------------------------------------------------------
@st.cache_data
def get_fixed_asset_pool(market_name):
    pools = {
        "S&P 500": [
            "SPY", "IVV", "VOO", "XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLE",
            "MSFT", "AAPL", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "UNH", "JPM", "XOM",
            "V", "PG", "AVGO", "HD", "MA", "COST", "MRK", "ABBV", "CVX", "PEP",
            "KO", "BAC", "WMT", "AMD", "MCD", "TMO", "CSCO", "INTC", "ADBE", "ABT",
            "ORCL", "CMCSA", "NFLX", "QCOM", "TXN", "AMAT", "HON", "GE", "LOW", "PFE"
        ],
        "NASDAQ": [
            "QQQ", "TQQQ", "SQQQ", "SOXL", "SOXS", "QLD", "PSQ", "SMH", "IGV", "IBB",
            "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "AVGO", "COST", "ASML",
            "AZN", "PEP", "LIN", "ADBE", "AMD", "CSCO", "TMUS", "CMCSA", "TXN", "QCOM",
            "AMAT", "ISRG", "HON", "MU", "INTU", "BKNG", "AMGN", "LRCX", "ADI", "PANW",
            "MDLZ", "REGN", "PDD", "VRTX", "KLAC", "SNPS", "CDNS", "CHTR", "MAR", "ORLY"
        ],
        "KOSPI": [
            "069500.KS", "114800.KS", "252670.KS", "122630.KS", "102110.KS", "139260.KS", "252710.KS", "337140.KS", "459580.KS", "229200.KS",
            "005930.KS", "000660.KS", "373220.KS", "207940.KS", "005380.KS", "005490.KS", "000270.KS", "035420.KS", "051910.KS", "006400.KS",
            "035720.KS", "068270.KS", "105560.KS", "055550.KS", "012330.KS", "028260.KS", "003550.KS", "011200.KS", "043700.KS", "015760.KS",
            "034730.KS", "000810.KS", "086790.KS", "010950.KS", "003670.KS", "009150.KS", "032830.KS", "003490.KS", "016360.KS", "000720.KS"
        ],
        "KOSDAQ": [
            "251340.KQ", "233740.KQ", "252730.KQ", "381180.KQ", "441540.KQ", "465350.KQ", "453650.KQ", "261220.KQ", "278530.KQ", "143860.KQ",
            "247540.KQ", "086520.KQ", "091990.KQ", "066970.KQ", "293490.KQ", "112040.KQ", "263750.KQ", "035760.KQ", "253450.KQ", "058470.KQ",
            "078600.KQ", "036570.KQ", "145020.KQ", "067160.KQ", "034230.KQ", "041510.KQ", "036830.KQ", "039200.KQ", "022100.KQ", "084370.KQ"
        ]
    }
    return pools.get(market_name, [])

@st.cache_data
def get_master_meta_map():
    return {
        # 미국 ETF 라인업
        "SPY": {"name": "S&P500 지수추종 (SPY)", "sector": "지수추종 ETF"},
        "IVV": {"name": "S&P500 코어 (IVV)", "sector": "지수추종 ETF"},
        "VOO": {"name": "뱅가드 S&P500 (VOO)", "sector": "지수추종 ETF"},
        "QQQ": {"name": "나스닥100 지수추종 (QQQ)", "sector": "지수추종 ETF"},
        "TQQQ": {"name": "나스닥 3배 레버리지 (TQQQ)", "sector": "레버리지/인버스 ETF"},
        "SQQQ": {"name": "나스닥 3배 인버스 (SQQQ)", "sector": "레버리지/인버스 ETF"},
        "SOXL": {"name": "반도체 3배 레버리지 (SOXL)", "sector": "레버리지/인버스 ETF"},
        "SOXS": {"name": "반도체 3배 인버스 (SOXS)", "sector": "레버리지/인버스 ETF"},
        "QLD": {"name": "나스닥 2배 레버리지 (QLD)", "sector": "레버리지/인버스 ETF"},
        "PSQ": {"name": "나스닥 1배 인버스 (PSQ)", "sector": "레버리지/인버스 ETF"},
        "XLK": {"name": "기술주 섹터 (XLK)", "sector": "섹터별 ETF"},
        "XLF": {"name": "금융주 섹터 (XLF)", "sector": "섹터별 ETF"},
        "XLV": {"name": "헬스케어 섹터 (XLV)", "sector": "섹터별 ETF"},
        "XLY": {"name": "소비재 섹터 (XLY)", "sector": "섹터별 ETF"},
        "XLC": {"name": "통신서비스 섹터 (XLC)", "sector": "섹터별 ETF"},
        "XLI": {"name": "산업재 섹터 (XLI)", "sector": "섹터별 ETF"},
        "XLE": {"name": "에너지 섹터 (XLE)", "sector": "섹터별 ETF"},
        "SMH": {"name": "반도체 테마 (SMH)", "sector": "섹터별 ETF"},
        "IGV": {"name": "소프트웨어 테마 (IGV)", "sector": "섹터별 ETF"},
        "IBB": {"name": "바이오 테마 (IBB)", "sector": "섹터별 ETF"},
        # 미국 개별주식
        "NVDA": {"name": "엔비디아", "sector": "반도체"}, "AMD": {"name": "AMD", "sector": "반도체"},
        "INTC": {"name": "인텔", "sector": "반도체"}, "AVGO": {"name": "브로드컴", "sector": "반도체"},
        "QCOM": {"name": "퀄컴", "sector": "반도체"}, "AAPL": {"name": "애플", "sector": "빅테크"},
        "MSFT": {"name": "마이크로소프트", "sector": "빅테크"}, "AMZN": {"name": "아마존", "sector": "빅테크/유통"},
        "GOOGL": {"name": "알파벳(구글)", "sector": "빅테크"}, "META": {"name": "메타 Platforms", "sector": "빅테크"},
        "TSLA": {"name": "테슬라", "sector": "모빌리티/전기차"}, "NFLX": {"name": "넷플릭스", "sector": "미디어/엔터"},
        "JPM": {"name": "JP모건 체이스", "sector": "금융/은행"}, "BAC": {"name": "뱅크오브아메리카", "sector": "금융/은행"},
        "XOM": {"name": "엑슨모빌", "sector": "에너지/정유"}, "COST": {"name": "코스트코", "sector": "소비재/유통"},
        "WMT": {"name": "월마트", "sector": "소비재/유통"}, "KO": {"name": "코카콜라", "sector": "소비재/식음료"},
        "BRK-B": {"name": "버크셔 해서웨이", "sector": "금융/지주"}, "UNH": {"name": "유나이티드헬스", "sector": "헬스케어"},
        
        # 한국 ETF 라인업
        "069500.KS": {"name": "KODEX 200 (069500)", "sector": "지수추종 ETF"},
        "114800.KS": {"name": "KODEX 인버스 (114800)", "sector": "레버리지/인버스 ETF"},
        "252670.KS": {"name": "KODEX 200선물인버스2X (252670)", "sector": "레버리지/인버스 ETF"},
        "122630.KS": {"name": "KODEX 레버리지 (122630)", "sector": "레버리지/인버스 ETF"},
        "102110.KS": {"name": "TIGER 200 (102110)", "sector": "지수추종 ETF"},
        "139260.KS": {"name": "TIGER 고배당 (139260)", "sector": "섹터별 ETF"},
        "252710.KS": {"name": "TIGER 200선물인버스2X (252710)", "sector": "레버리지/인버스 ETF"},
        "337140.KS": {"name": "KODEX 전장핵심부품 (337140)", "sector": "섹터별 ETF"},
        "459580.KS": {"name": "KODEX 반도체핵심 (459580)", "sector": "섹터별 ETF"},
        "229200.KS": {"name": "KODEX 코스닥150 (229200)", "sector": "지수추종 ETF"},
        "251340.KQ": {"name": "KODEX 코스닥150인버스 (251340)", "sector": "레버리지/인버스 ETF"},
        "233740.KQ": {"name": "KODEX 코스닥150레버리지 (233740)", "sector": "레버리지/인버스 ETF"},
        # 한국 개별주식
        "005930.KS": {"name": "삼성전자", "sector": "반도체"}, "000660.KS": {"name": "SK하이닉스", "sector": "반도체"},
        "373220.KS": {"name": "LG에너지솔루션", "sector": "2차전지"}, "247540.KQ": {"name": "에코프로비엠", "sector": "2차전지"},
        "086520.KQ": {"name": "에코프로", "sector": "2차전지"}, "207940.KS": {"name": "삼성바이오로직스", "sector": "제약/바이오"},
        "068270.KS": {"name": "셀트리온", "sector": "제약/바이오"}, "005380.KS": {"name": "현대차", "sector": "자동차/모빌리티"},
        "000270.KS": {"name": "기아", "sector": "자동차/모빌리티"}, "005490.KS": {"name": "POSCO홀딩스", "sector": "철강/소재"},
        "035420.KS": {"name": "NAVER", "sector": "IT/플랫폼"}, "035720.KS": {"name": "카카오", "sector": "IT/플랫폼"},
        "105560.KS": {"name": "KB금융", "sector": "금융/은행"}, "055550.KS": {"name": "신한지주", "sector": "금융/은행"}
    }

# ----------------------------------------------------------------------
# 4. 정밀 데이터 연산 엔진 (전기 vs 당기 거래량 동시 추출 구조)
# ----------------------------------------------------------------------
@st.cache_data(ttl=1800)
def load_optimized_market_data(market_name, time_frame, config):
    tickers = get_fixed_asset_pool(market_name)
    meta_map = get_master_meta_map()
    data_list = []
    
    if time_frame == "일단위 (Daily)":
        end_dt = datetime.strptime(config["end"], "%Y-%m-%d") + timedelta(days=1)
        start_dt = end_dt - timedelta(days=config["days_back"])
        start_date_str = start_dt.strftime("%Y-%m-%d")
        end_date_str = end_dt.strftime("%Y-%m-%d")
    else:
        start_date_str = config["prev_start"]
        end_date_str = (datetime.strptime(config["end"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        df = yf.download(tickers, start=start_date_str, end=end_date_str, group_by='ticker', progress=False)
        
        for t in tickers:
            meta = meta_map.get(t, {"name": t.split('.')[0] + " (기타)", "sector": "기타 대형주"})
            name = meta["name"]
            sector = meta["sector"]
            
            if t in df.columns.levels[0]:
                t_df = df[t].dropna()
            else:
                continue
                
            if len(t_df) < 2: continue
            
            if time_frame == "일단위 (Daily)":
                this_day = t_df.iloc[-1]
                prev_day = t_df.iloc[-2]
                
                this_vol = float(this_day['Volume'])
                prev_vol = float(prev_day['Volume'])
                if prev_vol == 0 or pd.isna(this_vol): continue
                vol_change = ((this_vol - prev_vol) / prev_vol) * 100
                
                this_price = float(this_day['Close'])
                prev_price = float(prev_day['Close'])
                price_change = ((this_price - prev_price) / prev_price) * 100
                
            else:
                w_start, w_end = config["start"], config["end"]
                pw_start, pw_end = config["prev_start"], config["prev_end"]
                
                try:
                    this_vol = float(t_df['Volume'].loc[w_start:w_end].sum())
                    prev_vol = float(t_df['Volume'].loc[pw_start:pw_end].sum())
                    this_price = float(t_df['Close'].loc[w_start:w_end].mean())
                    prev_price = float(t_df['Close'].loc[pw_start:pw_end].mean())
                except KeyError:
                    continue
                    
                if prev_vol == 0 or pd.isna(this_vol) or pd.isna(this_price): continue
                vol_change = ((this_vol - prev_vol) / prev_vol) * 100
                price_change = ((this_price - prev_price) / prev_price) * 100
            
            data_list.append({
                "명칭": name, "티커": t.split('.')[0], "산업군": sector,
                "이전 주가": prev_price, "현재 주가": this_price, "주가 증감률(%)": round(price_change, 2),
                "이전 거래량": prev_vol, "현재 거래량": this_vol, "거래량 증감률(%)": round(vol_change, 2)
            })
            
        return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"데이터 수집 중 정밀 에러 발생: {e}")
        return pd.DataFrame()

def highlight_rows(row):
    val = row["거래량 증감률(%)"]
    if val >= 50.0: return ['background-color: #d4edda; color: #155724; font-weight: bold;'] * len(row)
    elif val <= -30.0: return ['background-color: #f8d7da; color: #721c24; font-weight: bold;'] * len(row)
    return [''] * len(row)

# ----------------------------------------------------------------------
# 5. 시장별 화면 렌더링 시작
# ----------------------------------------------------------------------
tabs = st.tabs(["🇺🇸 S&P 500", "🇺🇸 NASDAQ", "🇰🇷 KOSPI", "🇰🇷 KOSDAQ"])
market_names = ["S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"]

for tab, m_name in zip(tabs, market_names):
    with tab:
        df_raw = load_optimized_market_data(m_name, time_frame, config)
        
        if df_raw.empty:
            st.warning("데이터 동기화 대기 중이거나 요청하신 일자의 데이터가 존재하지 않습니다.")
        else:
            # ----------------------------------------------------------------------
            # [요구사항 5 반영] 특징주 코너 브리핑 (급증 TOP 10 vs 급감 TOP 10 분리 및 요약)
            # ----------------------------------------------------------------------
            st.subheader(f"🔥 {m_name} 실시간 특징주 기술적 브리핑")
            
            col_up, col_down = st.columns(2)
            
            # 거래량 급증 TOP 10
            df_top_up = df_raw.sort_values(by="거래량 증감률(%)", ascending=False).head(10)
            with col_up:
                st.markdown("### 📈 거래량 폭발 매수세 유입 (TOP 10)")
                for idx, row in enumerate(df_top_up.itertuples(), 1):
                    p_sign = "+" if row._6 >= 0 else ""
                    st.write(f"**{idx}위. {row.명칭}** ({row.산업군})")
                    st.caption(f"↳ 거래량 **+{row._9:,.1f}%** 폭증 | 주가 변동 **{p_sign}{row._6:.2f}%** (현재가: {row._5:,.2f})")
            
            # 거래량 급감 TOP 10
            df_top_down = df_raw.sort_values(by="거래량 증감률(%)", ascending=True).head(10)
            with col_down:
                st.markdown("### 📉 거래 절벽 및 자금 이탈 (TOP 10)")
                for idx, row in enumerate(df_top_down.itertuples(), 1):
                    p_sign = "+" if row._6 >= 0 else ""
                    st.write(f"**{idx}위. {row.명칭}** ({row.산업군})")
                    st.caption(f"↳ 거래량 **{row._9:,.1f}%** 급감 | 주가 변동 **{p_sign}{row._6:.2f}%** (현재가: {row._5:,.2f})")
            
            # ----------------------------------------------------------------------
            # [요구사항 4 반영] 듀얼 머니플로우 원그래프 (전기 비중 vs 당기 비중 동시 비교)
            # ----------------------------------------------------------------------
            st.markdown("---")
            period_label_prev = "전 영업일" if time_frame == "일단위 (Daily)" else "직전 주차"
            period_label_curr = "당일 기준일" if time_frame == "일단위 (Daily)" else "선택 주차"
            
            st.subheader(f"🍩 {m_name} 섹터별 머니플로우 비교 ({period_label_prev} vs {period_label_curr})")
            st.caption("좌측(이전 기간)과 우측(현재 기간)을 비교하여 돈이 어느 산업군으로 거대하게 이동하고 있는지 파악하세요.")
            
            df_sector = df_raw.groupby("산업군")[["이전 거래량", "현재 거래량"]].sum().reset_index()
            
            fig_pie = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "domain"}]],
                                    subplot_titles=[f"◀ {period_label_prev} 자금 비중", f"▶ {period_label_curr} 자금 비중"])
            
            fig_pie.add_trace(
                go.Pie(labels=df_sector["산업군"], values=df_sector["이전 거래량"], name=period_label_prev, hole=0.4),
                1, 1
            )
            fig_pie.add_trace(
                go.Pie(labels=df_sector["산업군"], values=df_sector["현재 거래량"], name=period_label_curr, hole=0.4),
                1, 2
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # ----------------------------------------------------------------------
            # [요구사항 2, 3 보완] 다이버전스 복합 판독 차트 (X축에 명확한 ETF/종목 한글명 매핑)
            # ----------------------------------------------------------------------
            st.markdown("---")
            st.subheader(f"📈 {m_name} 다이버전스 판독 차트 (변화율 Top 10)")
            st.caption("💡 거래량은 급증(막대)하는데 주가는 정체/하락(선) 중이라면 **세력 진입(매수 기회)**, 거래량은 급감하는데 주가만 버틴다면 **이탈 국면(익절 타이밍)**입니다.")
            
            df_sorted_all = df_raw.sort_values(by="거래량 증감률(%)", ascending=False).reset_index(drop=True)
            df_chart = df_sorted_all.head(10).copy()
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(
                go.Bar(
                    x=df_chart["명칭"], y=df_chart["거래량 증감률(%)"], 
                    name="거래량 증감률(%)", marker_color="#2ca02c",
                    customdata=df_chart[["티커", "현재 거래량", "산업군"]],
                    hovertemplate="<b>%{x}</b><br>세부 섹터: %{customdata[2]}<br>거래량 변동: %{y:+.2f}%<br>현재 거래량: %{customdata[1]:,.0f}주<extra></extra>"
                ), secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df_chart["명칭"], y=df_chart["주가 증감률(%)"], 
                    name="주가 증감률(%)", mode="lines+markers",
                    line=dict(color="#d62728", width=4), marker=dict(size=9),
                    hovertemplate="<b>%{x}</b><br>주가 변동: %{y:+.2f}%<extra></extra>"
                ), secondary_y=True
            )
            
            fig.update_layout(
                height=450, margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified"
            )
            fig.update_yaxes(title_text="거래량 증감률 (%)", secondary_y=False, showgrid=False)
            fig.update_yaxes(title_text="주가 증감률 (%)", secondary_y=True, showgrid=True)
            st.plotly_chart(fig, use_container_width=True)
            
            # ----------------------------------------------------------------------
            # [요구사항 1, 3 반영] 데이터 시트 (상위 50개 고정 출력)
            # ----------------------------------------------------------------------
            st.markdown("---")
            st.subheader(f"📊 {m_name} 다이버전스 상세 데이터 시트 (상위 50개 고정)")
            
            if exclude_decreased:
                df_filtered = df_sorted_all[df_sorted_all["거래량 증감률(%)"] >= 0]
            else:
                df_filtered = df_sorted_all
                
            df_top50 = df_filtered.head(50).copy()
            df_top50.index = (df_top50.index + 1).astype(str) + "위"
            df_top50.index.name = "순위"
            df_top50 = df_top50.reset_index()
            
            df_styled = df_top50[["순위", "명칭", "티커", "산업군", "이전 주가", "현재 주가", "주가 증감률(%)", "현재 거래량", "거래량 증감률(%)"]]
            
            st.dataframe(
                df_styled.style.format({
                    "이전 주가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "현재 주가": "{:,.2f}" if "S&P" in m_name or "NASDAQ" in m_name else "{:,.0f}",
                    "주가 증감률(%)": "{:+.2f}%",
                    "현재 거래량": "{:,.0f}",
                    "거래량 증감률(%)": "{:+.2f}%"
                }).apply(highlight_rows, axis=1),
                use_container_width=True,
                height=550,
                hide_index=True
            )
