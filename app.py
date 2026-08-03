import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="GBP Futures Signal Dashboard", layout="wide")

st.title("GBP Futures Signal Dashboard")
st.write("This dashboard uses GBP/USD as a proxy for British pound futures.")

# -----------------------------
# Sidebar settings
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
# Data download function
# -----------------------------
@st.cache_data(ttl=300)
def get_data(symbol, period, interval):
    data = yf.download(symbol, period=period, interval=interval, progress=False)
    if data.empty:
        return pd.DataFrame()
    data = data.dropna()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

def last_close(data):
    if data.empty:
        return np.nan
    return float(data["Close"].iloc[-1])

# -----------------------------
# Technical score
# -----------------------------
def calculate_technical_score(data):
    if data.empty or len(data) < 50:
        return 0, ["Not enough GBP/USD data for technical score."]

    df = data.copy()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["Momentum5"] = df["Close"] - df["Close"].shift(5)

    latest = df.iloc[-1]
    price = float(latest["Close"])
    ma20 = float(latest["MA20"])
    ma50 = float(latest["MA50"])
    momentum5 = float(latest["Momentum5"])

    score = 0
    notes = []

    if price > ma20 and price > ma50:
        score += 2
        notes.append("GBP/USD is above 20 MA and 50 MA: bullish.")
    elif price < ma20 and price < ma50:
        score -= 2
        notes.append("GBP/USD is below 20 MA and 50 MA: bearish.")
    else:
        notes.append("GBP/USD is between 20 MA and 50 MA: mixed.")

    if ma20 > ma50:
        score += 1
        notes.append("20 MA is above 50 MA: trend supports bulls.")
    elif ma20 < ma50:
        score -= 1
        notes.append("20 MA is below 50 MA: trend supports bears.")

    if momentum5 > 0:
        score += 1
        notes.append("5-period momentum is positive.")
    elif momentum5 < 0:
        score -= 1
        notes.append("5-period momentum is negative.")
    else:
        notes.append("5-period momentum is flat.")

    return score, notes

# -----------------------------
# Sentiment score
# -----------------------------
def change_over_periods(data, periods=5):
    if data.empty or len(data) <= periods:
        return np.nan
    return float(data["Close"].iloc[-1] - data["Close"].iloc[-1 - periods])

def calculate_sentiment_score(dxy_data, spx_data, vix_data):
    score = 0
    notes = []

    dxy_change = change_over_periods(dxy_data, 5)
    spx_change = change_over_periods(spx_data, 5)
    vix_change = change_over_periods(vix_data, 5)

    if not np.isnan(dxy_change):
        if dxy_change < 0:
            score += 2
            notes.append("DXY is falling over 5 periods: bullish for GBP.")
        elif dxy_change > 0:
            score -= 2
            notes.append("DXY is rising over 5 periods: bearish for GBP.")
        else:
            notes.append("DXY is flat.")
    else:
        notes.append("DXY data unavailable.")

    if not np.isnan(spx_change):
        if spx_change > 0:
            score += 1
            notes.append("S&P 500 is rising: risk-on tone supports GBP.")
        elif spx_change < 0:
            score -= 1
            notes.append("S&P 500 is falling: risk-off tone pressures GBP.")
        else:
            notes.append("S&P 500 is flat.")
    else:
        notes.append("S&P 500 data unavailable.")

    if not np.isnan(vix_change):
        if vix_change < 0:
            score += 1
            notes.append("VIX is falling: risk sentiment supports GBP.")
        elif vix_change > 0:
            score -= 1
            notes.append("VIX is rising: risk sentiment pressures GBP.")
        else:
            notes.append("VIX is flat.")
    else:
        notes.append("VIX data unavailable.")

    return score, notes

# -----------------------------
# Final signal
# -----------------------------
def get_final_signal(total_score, event_risk):
    if event_risk == "High Event Risk":
        return "No Trade - Event Risk"

    if total_score >= 5:
        return "Bullish"
    elif total_score <= -5:
        return "Bearish"
    else:
        return "Neutral"

# -----------------------------
# Load data
# -----------------------------
gbp_data = get_data(gbp_symbol, period, interval)
dxy_data = get_data(dxy_symbol, period, interval)
spx_data = get_data(spx_symbol, period, interval)
vix_data = get_data(vix_symbol, period, interval)

tech_score, tech_notes = calculate_technical_score(gbp_data)
sentiment_score, sentiment_notes = calculate_sentiment_score(dxy_data, spx_data, vix_data)

total_score = tech_score + sentiment_score + macro_score
signal = get_final_signal(total_score, event_risk)
confidence = min(100, abs(total_score) * 10)

# -----------------------------
# Dashboard metrics
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Current Signal", signal)

with col2:
    st.metric("Confidence", f"{confidence}%")

with col3:
    st.metric("Total Score", total_score)

with col4:
    price = last_close(gbp_data)
    st.metric("GBP/USD Proxy", "N/A" if np.isnan(price) else round(price, 5))

col5, col6, col7 = st.columns(3)

with col5:
    st.metric("Technical Score", tech_score)

with col6:
    st.metric("Sentiment Score", sentiment_score)

with col7:
    st.metric("Macro Score", macro_score)

# -----------------------------
# Chart
# -----------------------------
st.subheader("GBP/USD Proxy Chart")

if not gbp_data.empty:
    chart_df = gbp_data.copy()
    chart_df["MA20"] = chart_df["Close"].rolling(20).mean()
    chart_df["MA50"] = chart_df["Close"].rolling(50).mean()
    st.line_chart(chart_df[["Close", "MA20", "MA50"]])
else:
    st.error("GBP/USD data could not be loaded.")

# -----------------------------
# Notes
# -----------------------------
st.subheader("Technical Explanation")
for note in tech_notes:
    st.write("- " + note)

st.subheader("Sentiment Explanation")
for note in sentiment_notes:
    st.write("- " + note)

# -----------------------------
# Market snapshot
# -----------------------------
st.subheader("Market Snapshot")

snapshot = pd.DataFrame({
    "Market": ["GBP/USD Proxy", "DXY", "S&P 500", "VIX"],
    "Symbol": [gbp_symbol, dxy_symbol, spx_symbol, vix_symbol],
    "Last Close": [
        last_close(gbp_data),
        last_close(dxy_data),
        last_close(spx_data),
        last_close(vix_data)
    ]
})

st.dataframe(snapshot, use_container_width=True)

# -----------------------------
# Rules
# -----------------------------
st.subheader("Signal Rules")

st.write("Bullish if total score is 5 or higher.")
st.write("Bearish if total score is -5 or lower.")
st.write("Neutral if total score is between -4 and 4.")
st.write("High event risk overrides the score and returns No Trade - Event Risk.")

st.caption("Educational use only. This dashboard does not guarantee profitable trades.")
