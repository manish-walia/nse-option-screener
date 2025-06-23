import time
import pandas as pd
import streamlit as st
import requests
from datetime import datetime

# === CONFIG ===
symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"         # Replace with your Telegram bot token
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"         # Replace with your Telegram chat ID

# === TELEGRAM ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Telegram Error: {e}")

# === OPTION CHAIN FETCH ===
@st.cache_data(ttl=60)
def fetch_option_chain(symbol):
    try:
        url = f"https://web-production-9890.up.railway.app/option-chain/{symbol}"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Proxy returned status {response.status_code}")
        data = response.json()

        expiry = data['records']['expiryDates'][0]
        ce_data, pe_data = [], []

        for item in data['records']['data']:
            if 'CE' in item and 'PE' in item:
                ce = item['CE']
                pe = item['PE']
                ce["previousClose"] = ce.get("previousClose") or ce.get("lastPrice")
                pe["previousClose"] = pe.get("previousClose") or pe.get("lastPrice")
                ce_data.append(ce)
                pe_data.append(pe)

        return pd.DataFrame(ce_data), pd.DataFrame(pe_data), expiry

    except Exception as e:
        raise Exception(f"Error fetching data for {symbol}: {e}")

# === STRATEGY FILTERS ===
def apply_strategy(df, strategy):
    df = df.copy()
    df = df[df["totalTradedVolume"] > 0]
    df["oi_vol_ratio"] = df["changeinOpenInterest"] / df["totalTradedVolume"]

    if df.empty:
        return df

    avg_oi = df["changeinOpenInterest"].mean()
    avg_vol = df["totalTradedVolume"].mean()
    avg_oi_vol = df["oi_vol_ratio"].mean()

    if strategy == "Breakout":
        return df[(df["lastPrice"] > df["previousClose"]) & (df["oi_vol_ratio"] > avg_oi_vol)]
    elif strategy == "Reversal":
        return df[(df["lastPrice"] < df["previousClose"]) & (df["oi_vol_ratio"] > avg_oi_vol)]
    elif strategy == "Volume Spike":
        return df[df["totalTradedVolume"] > avg_vol * 1.5]
    elif strategy == "OI Surge":
        return df[df["changeinOpenInterest"] > avg_oi * 1.5]
    elif strategy == "Momentum":
        return df[(df["lastPrice"] > df["previousClose"] * 1.03) & (df["oi_vol_ratio"] > avg_oi_vol * 1.5)]

    return pd.DataFrame()

# === SIGNAL UI ===
def signal_card(row, side, expiry):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_price = row["lastPrice"]
    sl = round(last_price * 0.8, 2)
    tgt = round(last_price * 1.5, 2)
    return f"""
    <div style='background-color:black;padding:10px;border-radius:10px;margin:10px;color:white'>
        <b>📈 {side} {row['strikePrice']} ({row['symbol']})</b><br>
        🕒 <b>{now}</b> | Expiry: {expiry}<br>
        Entry: ₹{last_price} | SL: ₹{sl} | Target: ₹{tgt}<br>
        OI Change: {row['changeinOpenInterest']} | Vol: {row['totalTradedVolume']}<br>
        Prev Close: ₹{row['previousClose']} | OI/Vol: {round(row['oi_vol_ratio'], 2)}
    </div>
    """

# === STREAMLIT APP ===
st.set_page_config(page_title="📊 Option Screener", layout="wide")
st.title("📊 NSE Option Screener with Expert Strategy")

strategy = st.sidebar.selectbox("📌 Choose Strategy", ["Breakout", "Reversal", "Volume Spike", "OI Surge", "Momentum"])
show_raw_data = st.sidebar.checkbox("Show Raw CE/PE Data")

for sym in symbols:
    try:
        st.subheader(f"📍 {sym}")
        ce_df, pe_df, expiry = fetch_option_chain(sym)

        ce_df['symbol'] = sym
        pe_df['symbol'] = sym

        # Show quick metrics for debugging
        st.caption(f"🔍 CE Avg OI: {ce_df['changeinOpenInterest'].mean():.0f}, Avg Vol: {ce_df['totalTradedVolume'].mean():.0f}")
        st.caption(f"🔍 PE Avg OI: {pe_df['changeinOpenInterest'].mean():.0f}, Avg Vol: {pe_df['totalTradedVolume'].mean():.0f}")

        ce_filtered = apply_strategy(ce_df, strategy)
        pe_filtered = apply_strategy(pe_df, strategy)

        signals = pd.concat([ce_filtered, pe_filtered])

        if not signals.empty:
            for _, row in signals.iterrows():
                side = "CE" if row["strikePrice"] in ce_filtered["strikePrice"].values else "PE"
                card = signal_card(row, side, expiry)
                st.markdown(card, unsafe_allow_html=True)
                send_telegram_message(f"{sym} {side} {row['strikePrice']} Signal Hit!")
        else:
            st.info("📭 No signals found for this strategy right now.")

        if show_raw_data:
            with st.expander("🔍 CE Raw Data"):
                st.dataframe(ce_df)
            with st.expander("🔍 PE Raw Data"):
                st.dataframe(pe_df)

    except Exception as e:
        st.error(f"❌ Error fetching {sym}: {e}")