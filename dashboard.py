"""
=============================================================================
 퍼포먼스 마케팅 대시보드 v1.0
 Stack : Python 3.10+ / Streamlit / Plotly
 Author: Claude (Anthropic) — 경천님 요청 사양
=============================================================================

[실행 방법]
  pip install streamlit plotly pandas
  streamlit run dashboard.py

[데이터 구조]
  - 차원(Dimension) : 날짜, 매체, 광고유형
  - 지표(Metric)    : 광고비용, 전환수, 전환값(ROAS 계산용)
  - ROAS 공식       : (전환값 합계 / 광고비용 합계) * 100

[주요 컴포넌트]
  1. 샘플 데이터 생성기 (실제 운영 시 CSV/API 교체 포인트 명시)
  2. 다차원 필터 사이드바 (매체 · 광고유형 · 날짜 범위)
  3. KPI 요약 카드 (광고비용 · 전환수 · ROAS)
  4. 이중 축 복합 차트 (Bar: 광고비용 / Line: ROAS)
  5. 세그먼트별 테이블 (매체 × 광고유형 교차 집계)
=============================================================================
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# 0. 페이지 설정 — 반드시 최상단에 위치해야 함
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 1. 전역 CSS — 모던하고 미려한 디자인 토큰 정의
#    색상 팔레트: 다크 네이비 배경 + 인디고·민트 액센트
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* 구글 폰트: 헤드라인용 Plus Jakarta Sans */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

/* ── 전체 배경·폰트 ── */
html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
}

/* ── 앱 최상위 배경 ── */
.stApp {
    background-color: #0F1117;
    color: #E8EAF0;
}

/* ── 사이드바 ── */
section[data-testid="stSidebar"] {
    background-color: #161B27;
    border-right: 1px solid #252D3F;
}
section[data-testid="stSidebar"] .css-1d391kg { padding: 1.5rem 1rem; }

/* ── KPI 카드 컨테이너 ── */
.kpi-card {
    background: linear-gradient(145deg, #1A2035, #1E2840);
    border: 1px solid #2A3550;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    border-radius: 14px 0 0 14px;
}
.kpi-card.blue::before  { background: #4A6CF7; }
.kpi-card.mint::before  { background: #0ECAB8; }
.kpi-card.amber::before { background: #F79A4A; }

.kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6B7A9E;
    margin-bottom: 0.5rem;
}
.kpi-value {
    font-size: 1.9rem;
    font-weight: 700;
    color: #E8EAF0;
    line-height: 1;
}
.kpi-delta {
    font-size: 0.75rem;
    margin-top: 0.5rem;
    color: #0ECAB8;
}
.kpi-delta.neg { color: #F7624A; }

/* ── 섹션 타이틀 ── */
.section-title {
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #4A6CF7;
    margin-bottom: 0.5rem;
}

/* ── 차트 카드 ── */
.chart-card {
    background: #161B27;
    border: 1px solid #252D3F;
    border-radius: 16px;
    padding: 1.5rem;
}

/* Plotly 차트 배경 투명 처리 */
.js-plotly-plot .plotly { background: transparent !important; }

/* ── 데이터프레임 스타일 ── */
.stDataFrame { background: #161B27; border-radius: 12px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 2. 샘플 데이터 생성 함수
#    실제 운영 시: load_data() 내부를 
#    pd.read_csv("경로") 또는 API 호출로 교체
# ─────────────────────────────────────────────
@st.cache_data  # Streamlit 캐시: 필터 변경 시 데이터 재로드 방지
def load_data() -> pd.DataFrame:
    """
    샘플 광고 성과 데이터 생성기.
    
    컬럼 구조:
        date        : 날짜 (datetime)
        channel     : 매체 (Meta / Google / Kakao)
        ad_type     : 광고유형 (브랜드 / 퍼포먼스 / 리타겟팅)
        spend       : 광고비용 (원)
        conversions : 전환수
        conv_value  : 전환값 (원) — ROAS 계산에 사용
    """
    np.random.seed(42)  # 재현 가능한 난수 시드

    # 날짜 범위: 최근 90일
    date_range = pd.date_range(
        end=datetime.today().date(),
        periods=90,
        freq="D"
    )

    channels  = ["Meta", "Google", "Kakao"]
    ad_types  = ["브랜드", "퍼포먼스", "리타겟팅"]

    rows = []
    for date in date_range:
        for ch in channels:
            for ad in ad_types:
                # 매체별 기본 광고비 차등 설정 (현실감 부여)
                base_spend = {
                    "Meta": 800_000, "Google": 1_200_000, "Kakao": 500_000
                }[ch]

                # 광고유형별 배율 (퍼포먼스 > 리타겟팅 > 브랜드)
                type_mult = {"브랜드": 0.6, "퍼포먼스": 1.4, "리타겟팅": 1.0}[ad]

                # 주말 효과: 주말에 20% 상승
                weekend_mult = 1.2 if date.dayofweek >= 5 else 1.0

                spend = int(
                    base_spend * type_mult * weekend_mult
                    * np.random.uniform(0.8, 1.2)
                )

                # 전환수: 광고비 대비 비율 + 노이즈
                cvr_base = {"Meta": 0.0012, "Google": 0.0018, "Kakao": 0.0009}[ch]
                conversions = max(1, int(spend * cvr_base * np.random.uniform(0.7, 1.5)))

                # 전환값: 평균 객단가 × 전환수 (객단가에 노이즈 추가)
                avg_order = {
                    "브랜드": 65_000, "퍼포먼스": 45_000, "리타겟팅": 80_000
                }[ad]
                conv_value = int(conversions * avg_order * np.random.uniform(0.9, 1.1))

                rows.append({
                    "date": date,
                    "channel": ch,
                    "ad_type": ad,
                    "spend": spend,
                    "conversions": conversions,
                    "conv_value": conv_value,
                })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ─────────────────────────────────────────────
# 3. ROAS 가중평균 계산 유틸 함수
#    ※ 주의: 단순 평균이 아닌 가중평균(Weighted Average) 사용
#            → ROAS = Σ(전환값) / Σ(광고비) × 100
#    예) spend=[100, 200], roas=[500, 200]
#        단순평균 ROAS = 350  ← 오류 (비중 무시)
#        가중평균 ROAS = (100×500/100 + 200×200/100) / (100+200) × 100
#                     = (500 + 400) / 300 × 100 ≈ 300  ← 정확
# ─────────────────────────────────────────────
def calc_roas(df: pd.DataFrame) -> float:
    """DataFrame 내 광고비·전환값 합산 후 ROAS 계산."""
    total_spend = df["spend"].sum()
    if total_spend == 0:
        return 0.0
    return (df["conv_value"].sum() / total_spend) * 100


# ─────────────────────────────────────────────
# 4. 데이터 로드 및 사이드바 필터 UI 구성
# ─────────────────────────────────────────────
df_raw = load_data()

with st.sidebar:
    st.markdown("### ⚙️ 필터 설정")
    st.markdown("---")

    # 날짜 범위 선택
    st.markdown("**📅 날짜 범위**")
    min_date = df_raw["date"].min().date()
    max_date = df_raw["date"].max().date()
    default_start = max_date - timedelta(days=29)

    date_range_sel = st.date_input(
        label="기간 선택",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
        label_visibility="collapsed",
    )
    # 날짜 범위 선택 미완료 시 기본값 유지
    if isinstance(date_range_sel, tuple) and len(date_range_sel) == 2:
        start_date, end_date = date_range_sel
    else:
        start_date, end_date = default_start, max_date

    st.markdown("**📡 매체 선택**")
    channels_all = sorted(df_raw["channel"].unique().tolist())
    channels_sel = st.multiselect(
        label="매체",
        options=channels_all,
        default=channels_all,
        label_visibility="collapsed",
    )

    st.markdown("**🎯 광고유형 선택**")
    adtypes_all = sorted(df_raw["ad_type"].unique().tolist())
    adtypes_sel = st.multiselect(
        label="광고유형",
        options=adtypes_all,
        default=adtypes_all,
        label_visibility="collapsed",
    )

    st.markdown("**📊 차트 그룹 기준**")
    group_by = st.radio(
        label="그룹 기준",
        options=["전체 합산", "매체별", "광고유형별"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption(f"데이터 기간: {min_date} ~ {max_date}")
    st.caption(f"총 {len(df_raw):,}개 레코드")


# ─────────────────────────────────────────────
# 5. 필터 적용: 날짜 · 매체 · 광고유형 교차 필터링
# ─────────────────────────────────────────────
df = df_raw[
    (df_raw["date"] >= pd.Timestamp(start_date)) &
    (df_raw["date"] <= pd.Timestamp(end_date)) &
    (df_raw["channel"].isin(channels_sel if channels_sel else channels_all)) &
    (df_raw["ad_type"].isin(adtypes_sel if adtypes_sel else adtypes_all))
].copy()


# ─────────────────────────────────────────────
# 6. KPI 집계 — 선택 기간 전체 합산
# ─────────────────────────────────────────────
total_spend   = df["spend"].sum()
total_conv    = df["conversions"].sum()
total_roas    = calc_roas(df)

# 전전 기간 비교값 (델타 계산용)
delta_days = (end_date - start_date).days + 1
prev_start = start_date - timedelta(days=delta_days)
prev_end   = start_date - timedelta(days=1)

df_prev = df_raw[
    (df_raw["date"] >= pd.Timestamp(prev_start)) &
    (df_raw["date"] <= pd.Timestamp(prev_end))
]
prev_spend = df_prev["spend"].sum() if len(df_prev) > 0 else total_spend
prev_roas  = calc_roas(df_prev) if len(df_prev) > 0 else total_roas

# 광고비 증감률(%)
spend_delta_pct = ((total_spend - prev_spend) / prev_spend * 100) if prev_spend else 0
roas_delta_pct  = ((total_roas - prev_roas)  / prev_roas  * 100) if prev_roas  else 0


# ─────────────────────────────────────────────
# 7. 헤더 영역
# ─────────────────────────────────────────────
st.markdown("""
<div style="padding: 0.5rem 0 1.5rem;">
    <p style="font-size:0.75rem; letter-spacing:0.12em; text-transform:uppercase;
              color:#4A6CF7; font-weight:600; margin-bottom:0.3rem;">
        PERFORMANCE MARKETING
    </p>
    <h1 style="font-size:1.8rem; font-weight:700; color:#E8EAF0; margin:0; line-height:1.2;">
        광고 성과 대시보드
    </h1>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 8. KPI 카드 (3열 레이아웃)
# ─────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

# ── 광고비용 카드 ──
with col1:
    delta_class = "neg" if spend_delta_pct < 0 else ""
    delta_icon  = "▼" if spend_delta_pct < 0 else "▲"
    st.markdown(f"""
    <div class="kpi-card blue">
        <div class="kpi-label">💰 광고비용</div>
        <div class="kpi-value">₩{total_spend/1_000_000:.1f}M</div>
        <div class="kpi-delta {delta_class}">
            {delta_icon} {abs(spend_delta_pct):.1f}% vs 전기간
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── 전환수 카드 ──
with col2:
    st.markdown(f"""
    <div class="kpi-card mint">
        <div class="kpi-label">🎯 전환수</div>
        <div class="kpi-value">{total_conv:,}</div>
        <div class="kpi-delta">
            CPA ₩{int(total_spend/total_conv):,}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── ROAS 카드 ──
with col3:
    roas_class = "neg" if roas_delta_pct < 0 else ""
    roas_icon  = "▼" if roas_delta_pct < 0 else "▲"
    st.markdown(f"""
    <div class="kpi-card amber">
        <div class="kpi-label">📈 ROAS</div>
        <div class="kpi-value">{total_roas:.0f}%</div>
        <div class="kpi-delta {roas_class}">
            {roas_icon} {abs(roas_delta_pct):.1f}% vs 전기간
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 9. 이중 축 복합 차트 (Dual-axis Combo Chart)
#    - Bar  (좌측 Y축): 광고비용 (절대값 — 금액)
#    - Line (우측 Y축): ROAS (비율 — %)
#    
#    그룹 기준(group_by)에 따라 시리즈 분기:
#      · 전체 합산 → 단일 Bar + 단일 Line
#      · 매체별    → 매체 수만큼 Bar 시리즈 (stack) + ROAS Line
#      · 광고유형별 → 유형 수만큼 Bar 시리즈 (stack) + ROAS Line
# ─────────────────────────────────────────────

# ── 날짜별 집계 (그룹 기준 반영) ──
if group_by == "전체 합산":
    group_cols = ["date"]
elif group_by == "매체별":
    group_cols = ["date", "channel"]
else:  # 광고유형별
    group_cols = ["date", "ad_type"]

df_agg = (
    df.groupby(group_cols)
    .agg(
        spend     =("spend",       "sum"),
        conversions=("conversions", "sum"),
        conv_value=("conv_value",   "sum"),
    )
    .reset_index()
)
# 그룹별 ROAS 가중평균 계산
df_agg["roas"] = (df_agg["conv_value"] / df_agg["spend"] * 100).round(1)

# ── 컬러 팔레트 정의 (매체·유형별 고정 색상) ──
COLOR_MAP = {
    # 매체
    "Meta"      : "#4A6CF7",  # 인디고
    "Google"    : "#0ECAB8",  # 민트
    "Kakao"     : "#F7C94A",  # 옐로우
    # 광고유형
    "브랜드"    : "#A78BFA",  # 퍼플
    "퍼포먼스"  : "#34D399",  # 그린
    "리타겟팅"  : "#F97316",  # 오렌지
    # 전체 합산
    "전체"      : "#4A6CF7",
}
ROAS_COLOR = "#FF6B6B"  # ROAS 라인은 항상 레드 계열로 구분

# ── Plotly Figure 생성 ──
fig = go.Figure()

# 그룹 시리즈 결정
if group_by == "전체 합산":
    segments = ["전체"]
    seg_col  = None
elif group_by == "매체별":
    segments = sorted(df_agg["channel"].unique())
    seg_col  = "channel"
else:
    segments = sorted(df_agg["ad_type"].unique())
    seg_col  = "ad_type"

# ── Bar 시리즈: 광고비용 (좌측 Y축) ──
for seg in segments:
    if seg_col:
        mask      = df_agg[seg_col] == seg
        x_vals    = df_agg.loc[mask, "date"]
        y_spend   = df_agg.loc[mask, "spend"]
    else:
        # 전체 합산: 날짜별 단일 시리즈
        daily_agg = df_agg.groupby("date", as_index=False).agg(
            spend=("spend","sum"), conv_value=("conv_value","sum")
        )
        daily_agg["roas"] = (daily_agg["conv_value"] / daily_agg["spend"] * 100).round(1)
        df_agg = daily_agg  # 이후 ROAS 라인에서도 재사용
        x_vals  = df_agg["date"]
        y_spend = df_agg["spend"]

    fig.add_trace(go.Bar(
        name       = seg,
        x          = x_vals,
        y          = y_spend,
        yaxis      = "y1",                       # 좌측 Y축
        marker_color = COLOR_MAP.get(seg, "#888"),
        opacity    = 0.85,
        hovertemplate = (
            f"<b>{seg}</b><br>"
            "날짜: %{x|%Y-%m-%d}<br>"
            "광고비: ₩%{y:,.0f}<extra></extra>"
        ),
    ))

# ── ROAS Line 시리즈 (우측 Y축) ──
#    전체 ROAS는 가중평균으로 일별 재계산
if seg_col:
    roas_daily = (
        df_agg.groupby("date")
        .apply(lambda g: (g["conv_value"].sum() / g["spend"].sum() * 100)
               if g["spend"].sum() > 0 else 0)
        .reset_index(name="roas")
    )
    roas_x = roas_daily["date"]
    roas_y = roas_daily["roas"].round(1)
else:
    roas_x = df_agg["date"]
    roas_y = df_agg["roas"]

fig.add_trace(go.Scatter(
    name      = "ROAS (%)",
    x         = roas_x,
    y         = roas_y,
    yaxis     = "y2",                        # 우측 Y축
    mode      = "lines+markers",
    line      = dict(color=ROAS_COLOR, width=2.5),
    marker    = dict(size=5, color=ROAS_COLOR, line=dict(width=1.5, color="#0F1117")),
    hovertemplate = (
        "<b>ROAS</b><br>"
        "날짜: %{x|%Y-%m-%d}<br>"
        "ROAS: %{y:.1f}%<extra></extra>"
    ),
))

# ── 레이아웃 설정 ──
fig.update_layout(
    # 배경
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor  = "rgba(0,0,0,0)",

    # 폰트
    font = dict(family="Plus Jakarta Sans, sans-serif", color="#8A93B2", size=12),

    # 범례
    legend = dict(
        orientation = "h",
        yanchor     = "bottom",
        y           = 1.02,
        xanchor     = "left",
        x           = 0,
        font        = dict(size=11, color="#C0C8E0"),
        bgcolor     = "rgba(0,0,0,0)",
        bordercolor = "rgba(0,0,0,0)",
    ),

    # 막대 그룹 모드 (매체·유형별 → 누적)
    barmode = "stack" if group_by != "전체 합산" else "relative",

    # 좌측 Y축: 광고비용
    yaxis = dict(
        title      = "광고비용 (₩)",
        titlefont  = dict(color="#4A6CF7", size=11),
        tickfont   = dict(color="#6B7A9E", size=10),
        gridcolor  = "#1E2840",
        gridwidth  = 0.5,
        tickformat = ",.0f",
        tickprefix = "₩",
        showline   = False,
        zeroline   = False,
    ),

    # 우측 Y축: ROAS
    yaxis2 = dict(
        title      = "ROAS (%)",
        titlefont  = dict(color=ROAS_COLOR, size=11),
        tickfont   = dict(color="#6B7A9E", size=10),
        overlaying = "y",
        side       = "right",
        ticksuffix = "%",
        showgrid   = False,
        zeroline   = False,
        range      = [
            max(0, roas_y.min() * 0.85),
            roas_y.max() * 1.15
        ],
    ),

    # X축: 날짜
    xaxis = dict(
        tickfont    = dict(color="#6B7A9E", size=10),
        tickformat  = "%m/%d",
        gridcolor   = "#1E2840",
        gridwidth   = 0.3,
        showline    = False,
        zeroline    = False,
        rangeslider = dict(visible=False),
    ),

    # 여백
    margin = dict(l=10, r=10, t=60, b=40),

    # 호버모드
    hovermode = "x unified",

    # 높이
    height = 480,
)

# ── 차트 렌더링 ──
st.markdown('<div class="section-title">일별 광고비용 & ROAS 트렌드</div>', unsafe_allow_html=True)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────
# 10. 세그먼트 교차 분석 테이블
#     매체 × 광고유형 피벗 테이블
#     — 광고비, 전환수, ROAS 가중평균 표시
# ─────────────────────────────────────────────
st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-title">매체 × 광고유형 교차 분석</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["💰 광고비용", "🎯 전환수", "📈 ROAS"])

# 매체 × 광고유형 집계
seg_agg = (
    df.groupby(["channel", "ad_type"])
    .agg(spend=("spend","sum"), conversions=("conversions","sum"), conv_value=("conv_value","sum"))
    .reset_index()
)
seg_agg["roas"] = (seg_agg["conv_value"] / seg_agg["spend"] * 100).round(1)

with tab1:
    pivot_spend = seg_agg.pivot_table(
        index="channel", columns="ad_type", values="spend", aggfunc="sum", fill_value=0
    )
    pivot_spend.loc["합계"] = pivot_spend.sum()
    pivot_spend["합계"] = pivot_spend.sum(axis=1)
    # 숫자 포맷
    fmt_spend = pivot_spend.applymap(lambda v: f"₩{v/1_000_000:.1f}M")
    st.dataframe(fmt_spend, use_container_width=True)

with tab2:
    pivot_conv = seg_agg.pivot_table(
        index="channel", columns="ad_type", values="conversions", aggfunc="sum", fill_value=0
    )
    pivot_conv.loc["합계"] = pivot_conv.sum()
    pivot_conv["합계"] = pivot_conv.sum(axis=1)
    fmt_conv = pivot_conv.applymap(lambda v: f"{int(v):,}")
    st.dataframe(fmt_conv, use_container_width=True)

with tab3:
    # ROAS는 가중평균 계산 필요 → pivot 후 재계산
    pivot_roas_df = (
        seg_agg.groupby(["channel", "ad_type"])
        .apply(lambda g: (g["conv_value"].sum() / g["spend"].sum() * 100) if g["spend"].sum() > 0 else 0)
        .unstack(fill_value=0)
        .round(1)
    )
    # 합계 행: 전체 ROAS
    for ad in pivot_roas_df.columns:
        sub = df[df["ad_type"] == ad]
        pivot_roas_df.loc["합계", ad] = round(calc_roas(sub), 1)
    # 합계 열: 매체별 전체 ROAS
    for ch in df["channel"].unique():
        sub = df[df["channel"] == ch]
        pivot_roas_df.loc[ch, "합계"] = round(calc_roas(sub), 1)
    pivot_roas_df.loc["합계", "합계"] = round(total_roas, 1)

    fmt_roas = pivot_roas_df.applymap(lambda v: f"{v:.1f}%")
    st.dataframe(fmt_roas, use_container_width=True)


# ─────────────────────────────────────────────
# 11. 푸터
# ─────────────────────────────────────────────
st.markdown("""
<div style="margin-top:3rem; padding:1rem 0; border-top:1px solid #252D3F;
     text-align:center; font-size:0.72rem; color:#3A4560; letter-spacing:0.05em;">
    PERFORMANCE DASHBOARD · Built with Streamlit + Plotly · Data refreshes on filter change
</div>
""", unsafe_allow_html=True)
