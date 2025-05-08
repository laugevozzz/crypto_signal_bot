import ccxt
import pandas as pd
import schedule
import time
from telegram import Bot

# === SETTINGS ===
SYMBOLS = ['SOL/USDT', 'ETH/USDT']
TIMEFRAME = '1m'
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
FUNDING_THRESHOLD = 0  # Positive funding rate
TELEGRAM_TOKEN = '7568367607:AAECMh_e2_v9qjDQtHfPVaNfiLoZjxKoTOc'
CHAT_ID = '6327637333'

# === INIT ===
exchange = ccxt.binance()
exchange.options['defaultType'] = 'future'
bot = Bot(token=TELEGRAM_TOKEN)

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

    # LONG condition
    if ema_cross_long and rsi_oversold and funding_ok:
        message = f"🚀 LONG Signal on {symbol}\nEMA Cross ✅\nRSI = {last_row['rsi']:.2f}\nFunding = {funding_rate:.6f}"
        bot.send_message(chat_id=CHAT_ID, text=message)
        print(message)
    # SHORT condition
    elif ema_cross_short and rsi_overbought and funding_bearish:
        message = f"🔻 SHORT Signal on {symbol}\nEMA Cross ✅\nRSI = {last_row['rsi']:.2f}\nFunding = {funding_rate:.6f}"
        bot.send_message(chat_id=CHAT_ID, text=message)
        print(message)
    else:
        print(f"No signal on {symbol} | EMA: {ema_cross_long or ema_cross_short}, RSI <30: {rsi_oversold}, RSI >70: {rsi_overbought}, Funding: {funding_ok or funding_bearish}")

def run_bot():
    for symbol in SYMBOLS:
        check_signal(symbol)

# Schedule to run every minute
schedule.every(1).minutes.do(run_bot)

print("✅ Bot started... Running every 1 minute")

while True:
    schedule.run_pending()
    time.sleep(1)
