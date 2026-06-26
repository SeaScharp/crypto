import streamlit as st
import ccxt
import pandas as pd

from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


# =========================
# PAGE SETUP
# =========================

st.set_page_config(
    page_title="BloFin Crypto Signal Bot",
    page_icon="📈",
    layout="centered"
)

st.title("📈 BloFin Crypto Signal Bot")


# =========================
# INPUTS
# =========================

symbol_display = st.selectbox(
    "Trading Pair",
    ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
)

blofin_symbols = {
    "BTC/USDT": "BTC/USDT:USDT",
    "ETH/USDT": "ETH/USDT:USDT",
    "SOL/USDT": "SOL/USDT:USDT",
    "XRP/USDT": "XRP/USDT:USDT"
}

entry_timeframe = st.selectbox(
    "Entry Timeframe",
    ["5m", "15m", "30m", "1h"],
    index=1
)

trend_timeframe = st.selectbox(
    "Trend Timeframe",
    ["1h", "4h", "1d"],
    index=1
)

risk_reward = st.number_input(
    "Risk / Reward",
    min_value=1.0,
    max_value=10.0,
    value=2.0,
    step=0.5
)

account_balance = st.number_input(
    "Account Balance ($)",
    min_value=100.0,
    value=1000.0,
    step=100.0
)

risk_percent = st.number_input(
    "Risk Per Trade (%)",
    min_value=0.5,
    max_value=10.0,
    value=2.0,
    step=0.5
)

leverage = st.selectbox(
    "Leverage",
    [1, 2, 3, 5, 10, 15, 20, 25, 50],
    index=4
)


# =========================
# BLOFIN EXCHANGE
# =========================

def create_exchange():
    return ccxt.blofin({
        "enableRateLimit": True,
        "options": {
            "defaultType": "swap"
        }
    })


# =========================
# MARKET DATA
# =========================

@st.cache_data(ttl=60)
def get_market_data(symbol, timeframe, limit=300):
    exchange = create_exchange()

    exchange.load_markets()

    if symbol not in exchange.markets:
        available = [
            market for market in exchange.markets.keys()
            if "USDT" in market
        ]

        raise Exception(
            f"Symbol {symbol} not found on BloFin. "
            f"Example available symbols: {available[:10]}"
        )

    candles = exchange.fetch_ohlcv(
        symbol,
        timeframe,
        limit=limit
    )

    if not candles:
        raise Exception("No candle data returned from BloFin.")

    df = pd.DataFrame(
        candles,
        columns=["time", "open", "high", "low", "close", "volume"]
    )

    df["open"] = pd.to_numeric(df["open"], errors="coerce")
    df["high"] = pd.to_numeric(df["high"], errors="coerce")
    df["low"] = pd.to_numeric(df["low"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    df = df.dropna()

    if len(df) < 220:
        raise Exception(
            "Not enough candle data returned. Try a higher timeframe."
        )

    return df


# =========================
# INDICATORS
# =========================

def add_indicators(df):
    df["ema50"] = EMAIndicator(
        df["close"],
        window=50
    ).ema_indicator()

    df["ema200"] = EMAIndicator(
        df["close"],
        window=200
    ).ema_indicator()

    df["rsi"] = RSIIndicator(
        df["close"],
        window=14
    ).rsi()

    macd = MACD(df["close"])

    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    atr = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["atr"] = atr.average_true_range()

    df["volume_avg"] = df["volume"].rolling(
        window=20
    ).mean()

    df = df.dropna()

    return df


# =========================
# TREND DIRECTION
# =========================

def get_trend(df):
    latest = df.iloc[-1]

    if latest["ema50"] > latest["ema200"]:
        return "LONG"

    if latest["ema50"] < latest["ema200"]:
        return "SHORT"

    return "NO TRADE"


# =========================
# SIGNAL ENGINE
# =========================

def get_signal(entry_df, trend_direction):
    latest = entry_df.iloc[-1]
    previous = entry_df.iloc[-2]

    price = float(latest["close"])
    ema50 = float(latest["ema50"])
    rsi = float(latest["rsi"])
    macd = float(latest["macd"])
    macd_signal = float(latest["macd_signal"])
    atr = float(latest["atr"])
    volume = float(latest["volume"])
    volume_avg = float(latest["volume_avg"])

    score = 0

    if trend_direction == "LONG":
        if price > ema50:
            score += 1

        if 45 < rsi < 70:
            score += 1

        if macd > macd_signal:
            score += 1

        if volume > volume_avg:
            score += 1

        if latest["close"] > previous["close"]:
            score += 1

    elif trend_direction == "SHORT":
        if price < ema50:
            score += 1

        if 30 < rsi < 55:
            score += 1

        if macd < macd_signal:
            score += 1

        if volume > volume_avg:
            score += 1

        if latest["close"] < previous["close"]:
            score += 1

    else:
        return "NO TRADE", "WEAK", price, None, None, None, score

    if score >= 4:
        strength = "STRONG"
    elif score == 3:
        strength = "MODERATE"
    else:
        strength = "WEAK"

    if strength == "WEAK":
        return "NO TRADE", strength, price, None, None, None, score

    if trend_direction == "LONG":
        entry = price
        stop_loss = entry - (atr * 1.5)
        risk = entry - stop_loss
        take_profit = entry + (risk * risk_reward)

    else:
        entry = price
        stop_loss = entry + (atr * 1.5)
        risk = stop_loss - entry
        take_profit = entry - (risk * risk_reward)

    return trend_direction, strength, price, entry, stop_loss, take_profit, score


# =========================
# POSITION SIZE
# =========================

def calculate_position(entry, stop_loss):
    max_loss = account_balance * (risk_percent / 100)
    price_risk = abs(entry - stop_loss)

    if price_risk <= 0:
        return 0, 0, max_loss

    coin_amount = max_loss / price_risk
    position_value = coin_amount * entry
    margin_required = position_value / leverage

    return position_value, margin_required, max_loss


# =========================
# RUN APP
# =========================

if st.button("Get Signal"):

    try:
        with st.spinner("Analyzing BloFin market data..."):

            symbol = blofin_symbols[symbol_display]

            trend_df = get_market_data(
                symbol,
                trend_timeframe
            )

            entry_df = get_market_data(
                symbol,
                entry_timeframe
            )

            trend_df = add_indicators(trend_df)
            entry_df = add_indicators(entry_df)

            trend_direction = get_trend(trend_df)

            (
                direction,
                strength,
                current_price,
                entry,
                stop_loss,
                take_profit,
                score
            ) = get_signal(
                entry_df,
                trend_direction
            )

        st.divider()

        st.subheader(symbol_display)

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

        st.metric(
            "Signal Score",
            f"{score}/5"
        )

        if direction == "NO TRADE":
            st.warning("NO TRADE — market conditions are not strong enough.")

        else:
            position_value, margin_required, max_loss = calculate_position(
                entry,
                stop_loss
            )

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

            st.metric(
                "Position Size",
                f"${position_value:,.2f}"
            )

            st.metric(
                "Margin Required",
                f"${margin_required:,.2f}"
            )

            st.metric(
                "Maximum Loss",
                f"${max_loss:,.2f}"
            )

    except Exception as e:
        st.error(f"Error: {str(e)}")
