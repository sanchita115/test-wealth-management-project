import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from analyzer import parse_csv, compute_stats, detect_anomalies, generate_narrative
from dashboard import category_donut, daily_spending_area, top_merchants_bar, weekly_bar, kpi_metrics
from slack_notifier import send_anomaly_alerts

st.set_page_config(
    page_title="Bank Spending Analyzer",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600&family=Inconsolata:wght@400;600&display=swap');

    html, body, [class*="css"], p, span, div, label {
        font-family: 'Work Sans', Inter, system-ui, sans-serif !important;
        font-size: 14px;
        letter-spacing: -0.5px;
    }

    .stApp { background-color: #fef8fa; }
    .block-container { padding-top: 2rem; max-width: 1200px; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid rgba(0,0,0,0.08);
    }

    /* KPI cards */
    .kpi-card {
        background: #ffffff;
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 8px;
        padding: 20px 16px;
        text-align: center;
        box-shadow: 0 8px 12px -6px rgba(0,0,0,0.07);
    }
    .kpi-label {
        color: rgba(0,0,0,0.45);
        font-size: 11px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }
    .kpi-value {
        color: rgba(0,0,0,1);
        font-size: 22px;
        font-weight: 600;
        margin-top: 4px;
        font-family: 'Inconsolata', monospace !important;
        letter-spacing: -0.5px;
    }
    .kpi-value.positive { color: #119F97; }
    .kpi-value.negative { color: #FF5D39; }

    /* Narrative box */
    .narrative-box {
        background: #ffffff;
        border: 1px solid rgba(0,0,0,0.08);
        border-left: 3px solid #A43DF5;
        border-radius: 0 8px 8px 0;
        padding: 20px 24px;
        color: rgba(0,0,0,0.7);
        font-size: 14px;
        line-height: 1.75;
        box-shadow: 0 8px 12px -6px rgba(0,0,0,0.07);
    }

    /* Anomaly cards */
    .anomaly-card {
        background: rgba(253,43,104,0.04);
        border: 1px solid rgba(253,43,104,0.2);
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        color: rgba(0,0,0,0.7);
        font-size: 13px;
    }

    /* Headings */
    h1 {
        font-family: 'Work Sans', sans-serif !important;
        font-size: 30px !important;
        font-weight: 600 !important;
        color: rgba(0,0,0,1) !important;
        letter-spacing: -0.5px !important;
    }
    h2, h3 {
        font-family: 'Work Sans', sans-serif !important;
        font-weight: 600 !important;
        color: rgba(0,0,0,1) !important;
        letter-spacing: -0.5px !important;
    }

    /* Buttons */
    .stButton > button {
        background: #A43DF5;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 14px;
        font-weight: 500;
        font-family: 'Work Sans', sans-serif;
        letter-spacing: -0.5px;
        transition: background 150ms ease-in-out;
    }
    .stButton > button:hover { background: #880CE9; }

    /* Secondary / outline button style override for danger */
    .stButton > button[kind="secondary"] {
        background: white;
        color: #A43DF5;
        border: 1px solid rgba(0,0,0,0.15);
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background: #ffffff;
        border: 1px dashed rgba(0,0,0,0.15);
        border-radius: 8px;
    }

    /* Section headers */
    .section-header {
        font-size: 11px;
        font-weight: 600;
        color: rgba(0,0,0,0.45);
        margin: 24px 0 8px 0;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    /* Streamlit misc */
    .stTextInput > label { color: rgba(0,0,0,0.7) !important; font-size: 13px !important; }
    .stCheckbox > label { color: rgba(0,0,0,0.7) !important; font-size: 14px !important; }
    [data-testid="stMarkdownContainer"] p { color: rgba(0,0,0,0.7); font-size: 14px; }
    .stCaption, footer { color: rgba(0,0,0,0.45) !important; font-size: 12px !important; }

    /* Expander */
    [data-testid="stExpander"] {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 8px;
        background: #ffffff;
    }

    /* Divider */
    hr { border-color: rgba(0,0,0,0.08); }

    /* Dataframe */
    [data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


def render_kpi(label: str, value: str):
    css_class = "kpi-value"
    if value.startswith("+"):
        css_class += " positive"
    elif "₹-" in value:
        css_class += " negative"
    st.markdown(
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="{css_class}">{value}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")

    api_key = st.text_input(
        "Anthropic API Key",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Required for narrative generation",
    )
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    st.markdown("---")
    st.markdown("**Slack (optional)**")
    slack_token = st.text_input(
        "Slack Bot Token",
        value=os.getenv("SLACK_BOT_TOKEN", ""),
        type="password",
        placeholder="xoxb-...",
    )
    slack_channel = st.text_input(
        "Slack Channel ID",
        value=os.getenv("SLACK_CHANNEL_ID", ""),
        placeholder="C0XXXXXXXXX",
    )
    if slack_token:
        os.environ["SLACK_BOT_TOKEN"] = slack_token
    if slack_channel:
        os.environ["SLACK_CHANNEL_ID"] = slack_channel

    st.markdown("---")
    st.caption("Supports HDFC, SBI, ICICI, Axis, Kotak, Groww, INDmoney, and most standard CSV formats.")


# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("# Bank Spending Analyzer")
st.markdown('<p style="color:rgba(0,0,0,0.45); font-size:14px; margin-top:-8px;">Upload your bank CSV → narrative analysis, visual dashboard, Slack alerts</p>', unsafe_allow_html=True)
st.markdown("---")

uploaded_file = st.file_uploader(
    "Drop your bank statement CSV here",
    type=["csv"],
    help="Export from HDFC NetBanking, SBI, ICICI, Axis, Groww, INDmoney, or any standard bank CSV",
)

demo_mode = st.checkbox("No CSV? Use demo data", value=False)

if demo_mode and not uploaded_file:
    import io, random, numpy as np
    random.seed(42)
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", "2024-03-31", freq="D")
    rows = []
    merchants = [
        ("Swiggy", -1), ("Zomato", -1), ("Blinkit", -1), ("BigBasket", -1),
        ("Amazon", -1), ("Flipkart", -1), ("Myntra", -1), ("Nykaa", -1),
        ("Ola", -1), ("Uber", -1), ("Rapido", -1), ("IRCTC", -1),
        ("Airtel Postpaid", -1), ("Jio Recharge", -1),
        ("Netflix", -1), ("Hotstar", -1), ("Spotify", -1),
        ("Groww SIP", -1), ("Zerodha", -1),
        ("UPI/PhonePe", -1), ("UPI/GooglePay", -1),
        ("SALARY CREDIT NEFT", 1), ("ATM WITHDRAWAL", -1),
        ("BookMyShow", -1), ("PVR Cinemas", -1),
        ("Apollo Pharmacy", -1), ("Cult.fit", -1),
    ]
    for d in dates:
        n = random.randint(0, 3)
        for _ in range(n):
            merchant, sign = random.choice(merchants)
            if "SALARY" in merchant:
                if d.day == 1:
                    rows.append({"Date": d.strftime("%d/%m/%Y"), "Narration": merchant,
                                 "Amount": sign * round(random.uniform(65000, 75000), 2)})
            else:
                rows.append({"Date": d.strftime("%d/%m/%Y"), "Narration": merchant,
                             "Amount": sign * round(random.uniform(100, 4500), 2)})
    rows.append({"Date": "14/02/2024", "Narration": "Tanishq Jewellery", "Amount": -18500.00})
    rows.append({"Date": "01/03/2024", "Narration": "RENT NEFT TRANSFER", "Amount": -22000.00})
    rows.append({"Date": "10/03/2024", "Narration": "IndiGo Airlines IRCTC", "Amount": -8750.00})

    demo_df = pd.DataFrame(rows)
    uploaded_file = io.BytesIO(demo_df.to_csv(index=False).encode())
    st.info("Demo data loaded — 3 months of synthetic Indian bank transactions.")

if uploaded_file:
    with st.spinner("Parsing CSV..."):
        try:
            df = parse_csv(uploaded_file)
        except ValueError as e:
            st.error(f"CSV parsing error: {e}")
            st.stop()

    with st.spinner("Computing statistics..."):
        stats = compute_stats(df)
        anomalies = detect_anomalies(stats, df)

    # ── KPI Row ──
    st.markdown('<div class="section-header">Overview</div>', unsafe_allow_html=True)
    kpis = kpi_metrics(stats)
    cols = st.columns(len(kpis))
    for col, (label, value) in zip(cols, kpis.items()):
        with col:
            render_kpi(label, value)

    st.markdown("---")

    # ── Narrative ──
    st.markdown('<div class="section-header">AI Narrative Analysis</div>', unsafe_allow_html=True)

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning("Add your Anthropic API key in the sidebar to generate the narrative analysis.")
    else:
        if "narrative" not in st.session_state or st.button("Regenerate Analysis"):
            with st.spinner("Analysing your spending..."):
                try:
                    st.session_state.narrative = generate_narrative(stats, anomalies)
                except Exception as e:
                    st.session_state.narrative = f"Narrative generation failed: {e}"

        if "narrative" in st.session_state:
            st.markdown(
                f'<div class="narrative-box">{st.session_state.narrative.replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Anomalies ──
    if anomalies:
        st.markdown('<div class="section-header">Patterns & Anomalies</div>', unsafe_allow_html=True)
        emoji_map = {
            "spending_spike": "🚨", "category_dominance": "📊",
            "large_single_transaction": "💸", "week_over_week": "📈",
        }
        for a in anomalies:
            emoji = emoji_map.get(a["type"], "🔔")
            st.markdown(f'<div class="anomaly-card">{emoji} {a["message"]}</div>', unsafe_allow_html=True)

        if slack_token and slack_channel:
            if st.button("Send Alerts to Slack"):
                with st.spinner("Posting to Slack..."):
                    results = send_anomaly_alerts(anomalies, stats, slack_channel)
                for r in results:
                    st.success(r) if "Failed" not in r else st.error(r)
        else:
            st.caption("Add Slack credentials in the sidebar to push these alerts.")

    st.markdown("---")

    # ── Charts ──
    st.markdown('<div class="section-header">Dashboard</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(category_donut(stats), use_container_width=True)
    with col2:
        st.plotly_chart(top_merchants_bar(stats), use_container_width=True)

    st.plotly_chart(daily_spending_area(stats), use_container_width=True)
    st.plotly_chart(weekly_bar(stats), use_container_width=True)

    st.markdown("---")

    with st.expander("View raw transactions"):
        st.dataframe(
            df[["date", "description", "amount", "category"]].rename(columns={
                "date": "Date", "description": "Description",
                "amount": "Amount (₹)", "category": "Category",
            }).sort_values("Date", ascending=False),
            use_container_width=True,
            height=400,
        )

else:
    st.markdown("""
    <div style="text-align:center; padding: 48px 16px;">
        <div style="font-size:36px;">💳</div>
        <div style="font-size:18px; font-weight:600; color:rgba(0,0,0,0.7); margin-top:12px; letter-spacing:-0.5px;">
            Upload a bank CSV or enable demo mode to get started
        </div>
        <div style="margin-top:8px; color:rgba(0,0,0,0.45); font-size:13px;">
            Supports HDFC, SBI, ICICI, Axis, Kotak, Groww, INDmoney and most standard formats
        </div>
    </div>
    """, unsafe_allow_html=True)
