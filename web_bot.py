import ccxt
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from datetime import datetime
from zoneinfo import ZoneInfo

est_now = datetime.now(
    ZoneInfo("America/New_York")
)

st.caption(
    f"Current Eastern Time: {est_now.strftime('%Y-%m-%d %I:%M:%S %p')}"
)

st.set_page_config(page_title="Crypto Strategy Bot", layout="wide")

st.title("Crypto Strategy Bot")

symbol = st.selectbox(
    "Trading Pair",
    ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"],
    index=0
)

st.subheader("Trade Settings")

leverage = st.selectbox(
    "Leverage",
    [1, 2, 3, 5, 10, 15, 20, 25, 50],
    index=4
)

account_size = st.number_input("Account Balance ($)", value=1000.0)
risk_percent = st.number_input("Risk Per Trade (%)", value=2.0)

timeframe = st.selectbox(
    "Timeframe",
    ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
    index=2
)

limit = st.number_input(
    "Number of candles",
    min_value=250,
    max_value=1000,
    value=300
)

rsi_buy = st.number_input("RSI Long Below", value=40.0)
rsi_sell = st.number_input("RSI Short Above", value=60.0)

ema_fast = st.number_input("Fast EMA", value=50)
ema_slow = st.number_input("Slow EMA", value=200)

stop_loss_percent = st.number_input("Stop Loss %", value=1.0)
risk_reward = st.number_input("Risk Reward", value=2.0)


@st.cache_data(ttl=60)
def get_data(symbol, timeframe, limit):
    exchanges = [
        ("Binance", ccxt.binance),
        ("KuCoin", ccxt.kucoin),
        ("OKX", ccxt.okx),
    ]

    last_error = None

    for exchange_name, exchange_class in exchanges:
        try:
            exchange = exchange_class({
                "enableRateLimit": True,
                "timeout": 30000,
            })

            candles = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=int(limit)
            )

            df = pd.DataFrame(
                candles,
                columns=["time", "open", "high", "low", "close", "volume"]
            )

            df["time"] = pd.to_datetime(df["time"], unit="ms")
            return df, exchange_name

        except Exception as e:
            last_error = e
            continue

    st.error("Could not get data from Binance, KuCoin, or OKX.")
    st.info(str(last_error))
    st.stop()


def analyze(df):
    df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
    df["ema_fast"] = EMAIndicator(df["close"], window=int(ema_fast)).ema_indicator()
    df["ema_slow"] = EMAIndicator(df["close"], window=int(ema_slow)).ema_indicator()
    df["signal"] = ""

    for i in range(int(ema_slow), len(df)):
        rsi = df["rsi"].iloc[i]
        fast = df["ema_fast"].iloc[i]
        slow = df["ema_slow"].iloc[i]

        if fast > slow and rsi < rsi_buy:
            df.at[i, "signal"] = "LONG"

        elif fast < slow and rsi > rsi_sell:
            df.at[i, "signal"] = "SHORT"

    return df


def latest_signal(df):
    last = df.iloc[-1]
    price = last["close"]
    signal = last["signal"]

    if signal == "LONG":
        stop_loss = price * (1 - stop_loss_percent / 100)
        take_profit = price + ((price - stop_loss) * risk_reward)

    elif signal == "SHORT":
        stop_loss = price * (1 + stop_loss_percent / 100)
        take_profit = price - ((stop_loss - price) * risk_reward)

    else:
        stop_loss = None
        take_profit = None

    return signal, price, stop_loss, take_profit


def draw_chart(df):
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(df["time"], df["close"], label="Price")
    ax.plot(df["time"], df["ema_fast"], label=f"EMA {ema_fast}")
    ax.plot(df["time"], df["ema_slow"], label=f"EMA {ema_slow}")

    long_signals = df[df["signal"] == "LONG"]
    short_signals = df[df["signal"] == "SHORT"]

    ax.scatter(long_signals["time"], long_signals["close"], marker="^", s=100, label="LONG")
    ax.scatter(short_signals["time"], short_signals["close"], marker="v", s=100, label="SHORT")

    ax.set_title(f"{symbol} Strategy Chart")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")
    ax.legend()

    fig.autofmt_xdate()
    return fig


if st.button("Run Bot"):
    df, exchange_used = get_data(symbol, timeframe, limit)
    df = analyze(df)

    signal, price, stop_loss, take_profit = latest_signal(df)

    st.subheader("Latest Result")
    st.write("Exchange Used:", exchange_used)
    st.write("Price:", round(price, 2))
    st.write("Signal:", signal if signal else "WAIT")

    if stop_loss:
        st.write("Stop Loss:", round(stop_loss, 2))
        st.write("Take Profit:", round(take_profit, 2))

    st.subheader("Chart")
    st.pyplot(draw_chart(df))

    st.subheader("Latest Candles")
    st.dataframe(df.tail(20), use_container_width=True)

    st.warning("Educational use only. This is not financial advice.")
