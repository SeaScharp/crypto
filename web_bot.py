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

stop_loss_percent = st.number_input(
    "Stop Loss %",
    min_value=0.1,
    max_value=20.0,
    value=1.0,
    step=0.1
)

risk_reward = st.number_input(
    "Risk / Reward",
    min_value=1.0,
    max_value=10.0,
    value=2.0,
    step=0.5
)

# =====================================
# GET MARKET DATA
# =====================================

@st.cache_data(ttl=60)
def get_market_data(symbol, timeframe):

    exchange = ccxt.bybit({
        "enableRateLimit": True
    })

    candles = exchange.fetch_ohlcv(
        symbol,
        timeframe,
        limit=250
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
# ANALYZE TREND
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
# CALCULATE LEVELS
# =====================================

def calculate_levels(price, direction):

    if "LONG" in direction:

        entry = price

        stop_loss = entry * (
            1 - stop_loss_percent / 100
        )

        take_profit = entry + (
            (entry - stop_loss)
            * risk_reward
        )

        return entry, stop_loss, take_profit

    elif "SHORT" in direction:

        entry = price

        stop_loss = entry * (
            1 + stop_loss_percent / 100
        )

        take_profit = entry - (
            (stop_loss - entry)
            * risk_reward
        )

        return entry, stop_loss, take_profit

    return None, None, None

# =====================================
# SIGNAL BUTTON
# =====================================

if st.button("Get Signal"):

    try:

        with st.spinner("Analyzing market..."):

            df = get_market_data(
                symbol,
                timeframe
            )

            current_price, direction = analyze_market(df)

            entry, stop_loss, take_profit = calculate_levels(
                current_price,
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

        if entry:

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

        else:

            st.warning(
                "No trade setup found."
            )

    except Exception as e:

        st.error(
            f"Error: {str(e)}"
        )
