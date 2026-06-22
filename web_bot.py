import streamlit as st
import ccxt
import pandas as pd
from ta.trend import EMAIndicator

# =====================================
# PAGE CONFIG
# =====================================

st.set_page_config(
    page_title="Crypto Signal Dashboard",
    page_icon="📈",
    layout="centered"
)

st.title("📈 Crypto Signal Dashboard")

# =====================================
# INPUTS
# =====================================

symbol = st.selectbox(
    "Trading Pair",
    [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "XRP/USDT"
    ]
)

timeframe = st.selectbox(
    "Timeframe",
    [
        "5m",
        "15m",
        "30m",
        "1h",
        "4h",
        "1d"
    ],
    index=3
)

risk_reward = st.number_input(
    "Risk / Reward",
    min_value=1.0,
    max_value=10.0,
    value=2.0,
    step=0.5
)

# =====================================
# DATA DOWNLOAD
# =====================================

@st.cache_data(ttl=60)
def get_market_data(symbol, timeframe):
    exchange = ccxt.kraken({
        "enableRateLimit": True
    })

    candles = exchange.fetch_ohlcv(
        symbol,
        timeframe,
        limit=300
    )

    df = pd.DataFrame(
        candles,
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]
    )

    return df

# =====================================
# MARKET ANALYSIS
# =====================================

def analyze_market(df):

    df["ema50"] = EMAIndicator(
        df["close"],
        window=50
    ).ema_indicator()

    df["ema200"] = EMAIndicator(
        df["close"],
        window=200
    ).ema_indicator()

    latest = df.iloc[-1]

    current_price = float(latest["close"])

    ema50 = float(latest["ema50"])
    ema200 = float(latest["ema200"])

    if ema50 > ema200:
        direction = "LONG 🟢"

    elif ema50 < ema200:
        direction = "SHORT 🔴"

    else:
        direction = "WAIT 🟡"

    return current_price, direction

# =====================================
# SMART ENTRY CALCULATION
# =====================================

def calculate_levels(df, direction):

    recent_high = df["high"].tail(20).max()
    recent_low = df["low"].tail(20).min()

    if "LONG" in direction:

        entry = recent_low

        stop_loss = recent_low * 0.995

        risk = entry - stop_loss

        take_profit = entry + (
            risk * risk_reward
        )

        return entry, stop_loss, take_profit

    elif "SHORT" in direction:

        entry = recent_high

        stop_loss = recent_high * 1.005

        risk = stop_loss - entry

        take_profit = entry - (
            risk * risk_reward
        )

        return entry, stop_loss, take_profit

    return None, None, None

# =====================================
# SIGNAL STRENGTH
# =====================================

def get_signal_strength(df):

    latest = df.iloc[-1]

    ema50 = latest["ema50"]
    ema200 = latest["ema200"]

    gap = abs(
        ((ema50 - ema200) / ema200) * 100
    )

    if gap > 3:
        return "STRONG"

    elif gap > 1:
        return "MODERATE"

    return "WEAK"

# =====================================
# MAIN BUTTON
# =====================================

if st.button("Get Signal"):

    try:

        with st.spinner("Analyzing Market..."):

            df = get_market_data(
                symbol,
                timeframe
            )

            current_price, direction = analyze_market(df)

            strength = get_signal_strength(df)

            entry, stop_loss, take_profit = calculate_levels(
                df,
                direction
            )

        st.divider()

        st.subheader(symbol)

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Current Price",
                f"${current_price:,.4f}"
            )

        with col2:
            st.metric(
                "Market Direction",
                direction
            )

        st.metric(
            "Signal Strength",
            strength
        )

        if strength == "WEAK":
            st.warning(
                "No trade recommended. Trend is weak."
            )

        else:

            st.metric(
                "Best Entry",
                f"${entry:,.4f}"
            )

            st.metric(
                "Stop Loss",
                f"${stop_loss:,.4f}"
            )

            st.metric(
                "Take Profit",
                f"${take_profit:,.4f}"
            )

    except Exception as e:

        st.error(str(e))
