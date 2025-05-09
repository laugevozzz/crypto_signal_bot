import ccxt
import pandas as pd
import schedule
import time
import os
from dotenv import load_dotenv
from telegram import Bot

# === LOAD SETTINGS ===
load_dotenv()
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
TIMEFRAME = '1m'
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
FUNDING_THRESHOLD = 0
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")

# === INIT ===
exchange = ccxt.binance()
exchange.options['defaultType'] = 'future'
bot = Bot(token=TELEGRAM_TOKEN)

# System status message ved opstart
status_msg = (
    "📊 Bot-status:\n"
    "• Signal Bot: ✅ Aktiv\n"
    f"• Symboler: {', '.join(SYMBOLS)}\n"
    f"• Modtagere: {', '.join([id.strip() for id in CHAT_IDS if id.strip()])}"
)
for chat_id in CHAT_IDS:
    if chat_id.strip():
        bot.send_message(chat_id=chat_id.strip(), text=status_msg)

def fetch_ohlcv(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df):
    df['ema_fast'] = df['close'].ewm(span=EMA_FAST, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=EMA_SLOW, adjust=False).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def fetch_funding(symbol):
    market = exchange.market(symbol)
    funding = exchange.fapiPublicGetPremiumIndex({'symbol': market['id']})
    return float(funding['lastFundingRate'])

def check_signal(symbol):
    df = fetch_ohlcv(symbol)
    df = calculate_indicators(df)

    last_row = df.iloc[-1]
    ema_cross_long = last_row['ema_fast'] > last_row['ema_slow']
    ema_cross_short = last_row['ema_fast'] < last_row['ema_slow']
    rsi_oversold = last_row['rsi'] < 30
    rsi_overbought = last_row['rsi'] > 70
    funding_rate = fetch_funding(symbol)
    funding_ok = funding_rate > FUNDING_THRESHOLD
    funding_bearish = funding_rate < -FUNDING_THRESHOLD

    # LONG
    if ema_cross_long and rsi_oversold and funding_ok:
        message = f"🚀 LONG Signal på {symbol}\nEMA Cross: ✅\nRSI = {last_row['rsi']:.2f}\nFunding = {funding_rate:.6f}"
        for chat_id in CHAT_IDS:
            bot.send_message(chat_id=chat_id.strip(), text=message)
        print(message)

    # SHORT
    elif ema_cross_short and rsi_overbought and funding_bearish:
        message = f"🔻 SHORT Signal på {symbol}\nEMA Cross: ✅\nRSI = {last_row['rsi']:.2f}\nFunding = {funding_rate:.6f}"
        for chat_id in CHAT_IDS:
            bot.send_message(chat_id=chat_id.strip(), text=message)
        print(message)

    else:
        print(f"No signal on {symbol} | EMA: {ema_cross_long or ema_cross_short}, RSI: {last_row['rsi']:.2f}, Funding: {funding_rate:.6f}")

def run_bot():
    for symbol in SYMBOLS:
        check_signal(symbol)

schedule.every(1).minutes.do(run_bot)

print("✅ Signal bot kører hvert minut...")

while True:
    schedule.run_pending()
    time.sleep(1)

