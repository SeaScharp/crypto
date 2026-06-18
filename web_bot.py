import streamlit as st
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands

st.set_page_config(page_title="Crypto Trading Bot", layout="wide")

st.title("Crypto Trading Strategy Bot")
st.write("Simple crypto technical analysis using RSI, MACD, and Bollinger Bands.")

# Sidebar inputs
st.sidebar.header("Settings")

exchange_name = st.sidebar.selectbox(
    "Exchange",
    ["kraken", "coinbase", "kucoin"]
)

symbol = st.sidebar.selectbox(
    "Symbol",
    ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD"]
)

timeframe = st.sidebar.selectbox(
    "Timeframe",
    ["1m", "5m", "15m", "1h", "4h", "1d"],
    index=3
)

limit = st.sidebar.slider(
    "Number of candles",
    min_value=50,
    max_value=500,
    value=200
)

# Create exchange safely
try:
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class({
        "enableRateLimit": True,
        "timeout": 30000,
    })
except Exception as e:
    st.error(f"Could not load exchange: {e}")
    st.stop()

@st.cache_data(ttl=60)
def fetch_data(exchange_name, symbol, timeframe, limit):
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class({
        "enableRateLimit": True,
        "timeout": 30000,
    })

    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    df = pd.DataFrame(
        data,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

# Fetch market data
try:
    df = fetch_data(exchange_name, symbol, timeframe, limit)

except ccxt.base.errors.ExchangeNotAvailable:
    st.error("Exchange is not available right now, or Streamlit Cloud is blocked by this exchange.")
    st.info("Try another exchange from the dropdown, such as Kraken or Coinbase.")
    st.stop()

except ccxt.base.errors.NetworkError as e:
    st.error("Network error while connecting to the exchange.")
    st.info(str(e))
    st.stop()

except ccxt.base.errors.BadSymbol:
    st.error(f"The symbol {symbol} is not available on {exchange_name}. Try another exchange or symbol.")
    st.stop()

except Exception as e:
    st.error("Unexpected error while loading market data.")
    st.info(str(e))
    st.stop()

if df.empty:
    st.error("No data returned from the exchange.")
    st.stop()

# Technical indicators
df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()

macd = MACD(close=df["close"])
df["macd"] = macd.macd()
df["macd_signal"] = macd.macd_signal()

bb = BollingerBands(close=df["close"], window=20, window_dev=2)
df["bb_high"] = bb.bollinger_hband()
df["bb_low"] = bb.bollinger_lband()

latest = df.iloc[-1]

# Trading signal
signal = "HOLD"
reason = "No strong signal."

if latest["rsi"] < 30 and latest["macd"] > latest["macd_signal"]:
    signal = "BUY"
    reason = "RSI is oversold and MACD is bullish."

elif latest["rsi"] > 70 and latest["macd"] < latest["macd_signal"]:
    signal = "SELL"
    reason = "RSI is overbought and MACD is bearish."

# Display metrics
col1, col2, col3, col4 = st.columns(4)

col1.metric("Latest Price", round(latest["close"], 2))
col2.metric("RSI", round(latest["rsi"], 2))
col3.metric("MACD", round(latest["macd"], 4))
col4.metric("Signal", signal)

st.subheader("Signal Explanation")
st.write(reason)

# Price chart
st.subheader("Price Chart")

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df["timestamp"], df["close"], label="Close Price")
ax.plot(df["timestamp"], df["bb_high"], linestyle="--", label="Bollinger High")
ax.plot(df["timestamp"], df["bb_low"], linestyle="--", label="Bollinger Low")
ax.set_xlabel("Time")
ax.set_ylabel("Price")
ax.legend()
st.pyplot(fig)

# RSI chart
st.subheader("RSI Chart")

fig2, ax2 = plt.subplots(figsize=(12, 3))
ax2.plot(df["timestamp"], df["rsi"], label="RSI")
ax2.axhline(70, linestyle="--")
ax2.axhline(30, linestyle="--")
ax2.set_xlabel("Time")
ax2.set_ylabel("RSI")
ax2.legend()
st.pyplot(fig2)

# Data table
st.subheader("Recent Data")
st.dataframe(df.tail(20), use_container_width=True)

st.warning("Educational use only. This is not financial advice.")
