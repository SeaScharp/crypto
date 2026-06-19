import ccxt
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import anthropic

from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator


st.set_page_config(page_title="Crypto Strategy Bot", layout="wide")

st.title("Crypto Strategy Bot with Claude AI")

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

            df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
            df["time"] = df["time"].dt.tz_convert("America/Toronto")

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

    ax.scatter(
        long_signals["time"],
        long_signals["close"],
        marker="^",
        s=100,
        label="LONG"
    )

    ax.scatter(
        short_signals["time"],
        short_signals["close"],
        marker="v",
        s=100,
        label="SHORT"
    )

    ax.set_title(f"{symbol} Strategy Chart - Eastern Time")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")
    ax.legend()

    fig.autofmt_xdate()
    return fig


def claude_ai_analysis(
    symbol,
    timeframe,
    exchange_used,
    price,
    signal,
    rsi,
    ema_fast_value,
    ema_slow_value,
    stop_loss,
    take_profit,
    leverage,
    account_size,
    risk_percent
):
    client = anthropic.Anthropic(
        api_key=st.secrets["ANTHROPIC_API_KEY"]
    )

    prompt = f"""
You are analyzing a crypto trading setup for educational purposes only.

Trading Pair: {symbol}
Exchange Used: {exchange_used}
Timeframe: {timeframe}
Current Price: {price}
Signal: {signal}

RSI: {rsi}
Fast EMA: {ema_fast_value}
Slow EMA: {ema_slow_value}

Stop Loss: {stop_loss}
Take Profit: {take_profit}

Leverage: {leverage}x
Account Balance: ${account_size}
Risk Per Trade: {risk_percent}%

Explain in simple practical language:

1. Why the bot gave this signal
2. What the RSI means
3. What the EMA trend means
4. Whether this looks like high, medium, or low risk
5. What should be watched before entering
6. A clear warning that this is not financial advice

Do not promise profit.
Do not say the trade is guaranteed.
"""

    message = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1000,
        temperature=0.3,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return message.content[0].text


if st.button("Run Bot"):
    df, exchange_used = get_data(symbol, timeframe, limit)
    df = analyze(df)

    signal, price, stop_loss, take_profit = latest_signal(df)
    latest = df.iloc[-1]
    last_time = latest["time"]

    st.subheader("Latest Result")
    st.write("Exchange Used:", exchange_used)
    st.write("Last Candle Time:", last_time.strftime("%Y-%m-%d %I:%M %p %Z"))
    st.write("Price:", round(price, 2))
    st.write("Signal:", signal if signal else "WAIT")

    if stop_loss:
        st.write("Stop Loss:", round(stop_loss, 2))
        st.write("Take Profit:", round(take_profit, 2))

    st.subheader("Chart")
    st.pyplot(draw_chart(df))

    st.subheader("Latest Candles")
    st.dataframe(df.tail(20), use_container_width=True)

    st.subheader("Claude AI Analysis")

    if "ANTHROPIC_API_KEY" not in st.secrets:
        st.warning("Anthropic API key is missing. Add it in Streamlit Cloud Secrets.")
    else:
        with st.spinner("Claude is analyzing the setup..."):
            ai_result = claude_ai_analysis(
                symbol=symbol,
                timeframe=timeframe,
                exchange_used=exchange_used,
                price=round(price, 2),
                signal=signal if signal else "WAIT",
                rsi=round(latest["rsi"], 2),
                ema_fast_value=round(latest["ema_fast"], 2),
                ema_slow_value=round(latest["ema_slow"], 2),
                stop_loss=round(stop_loss, 2) if stop_loss else "N/A",
                take_profit=round(take_profit, 2) if take_profit else "N/A",
                leverage=leverage,
                account_size=account_size,
                risk_percent=risk_percent
            )

            st.write(ai_result)

    st.warning("Educational use only. This is not financial advice.")
