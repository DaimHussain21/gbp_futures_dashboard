import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="GBP Futures Signal Dashboard", layout="wide")

st.title("GBP Futures Signal Dashboard")
st.write("Educational signal dashboard using GBP/USD as a proxy for British pound futures.")

# -----------------------------
# User settings
# -----------------------------
st.sidebar.header("Settings")

gbp_symbol = st.sidebar.text_input("GBP/USD proxy symbol", "GBPUSD=X")
dxy_symbol = st.sidebar.text_input("DXY symbol", "DX-Y.NYB")
spx_symbol = st.sidebar.text_input("S&P 500 symbol", "^GSPC")
vix_symbol = st.sidebar.text_input("VIX symbol", "^VIX")

period = st.sidebar.selectbox("Data period", ["3mo", "6mo", "1y", "2y"], index=1)
interval = st.sidebar.selectbox("Interval", ["1d", "1h"], index=0)

macro_score = st.sidebar.slider("Manual Macro Score", -6, 6, 0)
event_risk = st.sidebar.selectbox("Event Risk", ["Normal", "High Event Risk"])

# -----------------------------
# Data functions
# -----------------------------
@st.cache_data(ttl=300)
def download_data(symbol, period, interval):
    data = yf.download(symbol, period=period, interval=interval, progress=False)
    if data.empty:
        return pd.DataFrame()
    # Newer yfinance versions can return MultiIndex columns even for a
    # single symbol (e.g. ("Close", "GBPUSD=X")). Flatten to plain columns.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.dropna()
    return data

def get_last_close(data):
    if data.empty:
        return np.nan
    return float(data["Close"].iloc[-1])

def calculate_indicators(data):
    df = data.copy()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["Momentum5"] = df["Close"] - df["Close"].shift(5)
    df["Returns"] = df["Close"].pct_change()
    df["Volatility20"] = df["Returns"].rolling(20).std() * np.sqrt(252)
    return df

def technical_score(df):
    if df.empty or len(df) < 50:
        return 0, ["Not enough data for technical score"]

    last = df.iloc[-1]
    price = float(last["Close"])
    ma20 = float(last["MA20"])
    ma50 = float(last["MA50"])
    momentum5 = float(last["Momentum5"])

    score = 0
    notes = []

    if price > ma20 and price > ma50:
        score += 2
        notes.append("Price is above 20 MA and 50 MA: bullish")
    elif price < ma20 and price < ma50:
        score -= 2
        notes.append("Price is below 20 MA and 50 MA: bearish")
    else:
        notes.append("Price is between major moving averages: neutral")

    if ma20 > ma50:
        score += 1
        notes.append("20 MA is above 50 MA: bullish trend")
    elif ma20 < ma50:
        score -= 1
        notes.append("20 MA is below 50 MA: bearish trend")

    if momentum5 > 0:
        score += 1
        notes.append("5-period momentum is positive: bullish")
    elif momentum5 < 0:
        score -= 1
        notes.append("5-period momentum is negative: bearish")

    return score, notes

def sentiment_score(dxy_df, spx_df, vix_df):
    score = 0
    notes = []

    def change_5(df):
        if df.empty or len(df) < 6:
            return np.nan
        return float(df["Close"].iloc[-1] - df["Close"].iloc[-6])

    dxy_change = change_5(dxy_df)
    spx_change = change_5(spx_df)
    vix_change = change_5(vix_df)

    if not np.isnan(dxy_change):
        if dxy_change < 0:
            score += 2
            notes.append("DXY is falling over 5 periods: bullish for GBP")
        elif dxy_change > 0:
            score -= 2
            notes.append("DXY is rising over 5 periods: bearish for GBP")

    if not np.isnan(spx_change):
        if spx_change > 0:
            score += 1
            notes.append("S&P 500 is rising: risk-on, supportive for GBP")
        elif spx_change < 0:
            score -= 1
            notes.append("S&P 500 is falling: risk-off, negative for GBP")

    if not np.isnan(vix_change):
        if vix_change < 0:
            score += 1
            notes.append("VIX is falling: risk-on, supportive for GBP")
        elif vix_change > 0:
            score -= 1
            notes.append("VIX is rising: risk-off, negative for GBP")

    return score, notes

def final_signal(total_score, event_risk):
    if event_risk == "High Event Risk":
        return "No Trade - Event Risk"
    if total_score >= 5:
        return "Bullish"
    elif total_score <= -5:
        return "Bearish"
    else:
        return "Neutral"

# -----------------------------
# Download data
# -----------------------------
gbp_data_raw = download_data(gbp_symbol, period, interval)
dxy_data_raw = download_data(dxy_symbol, period, interval)
spx_data_raw = download_data(spx_symbol, period, interval)
vix_data_raw = download_data(vix_symbol, period, interval)

gbp_data = calculate_indicators(gbp_data_raw) if not gbp_data_raw.empty else pd.DataFrame()

# -----------------------------
# Scores
# -----------------------------
tech_score, tech_notes = technical_score(gbp_data)
sent_score, sent_notes = sentiment_score(dxy_data_raw, spx_data_raw, vix_data_raw)

total_score = tech_score + sent_score + macro_score
signal = final_signal(total_score, event_risk)
confidence = min(100, abs(total_score) * 10)

# -----------------------------
# Display dashboard
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Current Signal", signal)

with col2:
    st.metric("Confidence", f"{confidence}%")

with col3:
    st.metric("Total Score", total_score)

with col4:
    st.metric("GBP/USD Proxy", round(get_last_close(gbp_data_raw), 5) if not gbp_data_raw.empty else "N/A")

col5, col6, col7 = st.columns(3)

with col5:
    st.metric("Technical Score", tech_score)

with col6:
    st.metric("Sentiment Score", sent_score)

with col7:
    st.metric("Macro Score", macro_score)

st.subheader("GBP/USD Proxy Chart")

if not gbp_data.empty:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=gbp_data.index,
        open=gbp_data["Open"],
        high=gbp_data["High"],
        low=gbp_data["Low"],
        close=gbp_data["Close"],
        name="GBP/USD"
    ))
    fig.add_trace(go.Scatter(x=gbp_data.index, y=gbp_data["MA20"], name="20 MA"))
    fig.add_trace(go.Scatter(x=gbp_data.index, y=gbp_data["MA50"], name="50 MA"))
    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No GBP/USD data loaded. Try changing symbol or interval.")

st.subheader("Score Explanation")

left, right = st.columns(2)

with left:
    st.write("Technical Notes")
    for note in tech_notes:
        st.write("- " + note)

with right:
    st.write("Sentiment Notes")
    for note in sent_notes:
        st.write("- " + note)

st.subheader("Market Data Snapshot")

snapshot = pd.DataFrame({
    "Market": ["GBP/USD", "DXY", "S&P 500", "VIX"],
    "Symbol": [gbp_symbol, dxy_symbol, spx_symbol, vix_symbol],
    "Last Close": [
        get_last_close(gbp_data_raw),
        get_last_close(dxy_data_raw),
        get_last_close(spx_data_raw),
        get_last_close(vix_data_raw)
    ]
})

st.dataframe(snapshot, use_container_width=True)

st.subheader("Signal Rules")

st.write("Bullish if total score is 5 or higher.")
st.write("Bearish if total score is -5 or lower.")
st.write("Neutral if total score is between -4 and 4.")
st.write("If event risk is high, the signal becomes No Trade - Event Risk.")

st.caption("This dashboard is for educational use only and does not guarantee trading results.")
