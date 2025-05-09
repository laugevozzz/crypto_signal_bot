import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
import json
from datetime import datetime
import os
from dotenv import load_dotenv
from telegram import Bot

# === Load .env for Telegram ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")

# Send systemstatus ved opstart
status_msg = (
    "📊 Bot-status:\n"
    "• News Sentiment: ✅ Aktiv\n"
    "• SignalBot: ⏳ Manuel overvågning\n"
    f"• Modtagere: {', '.join([id.strip() for id in CHAT_IDS if id.strip()])}"
)
bot = Bot(token=TELEGRAM_TOKEN)
for chat_id in CHAT_IDS:
    if chat_id.strip():
        bot.send_message(chat_id=chat_id.strip(), text=status_msg)

COINS = ["bitcoin", "ethereum", "solana"]
EXTRA_TERMS = ["crypto", "cryptocurrency", "altcoin", "web3"]
MACRO_TERMS = ["inflation", "interest rates", "recession", "federal reserve", "tariffs", "geopolitics", "regulation"]
GOOGLE_BASE_URL = "https://news.google.com/rss/search?q={query}+when:1d&hl=en-US&gl=US&ceid=US:en"
COINTELEGRAPH_URLS = {
    "bitcoin": "https://cointelegraph.com/rss/tag/bitcoin",
    "ethereum": "https://cointelegraph.com/rss/tag/ethereum",
    "solana": "https://cointelegraph.com/rss/tag/solana"
}
ADDITIONAL_FEEDS = {
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "TradingView": "https://www.tradingview.com/ideas/cryptocurrency/rss/"
}

sentiment_results = {}
alert_messages = []
sent_titles = set()

# --- Nyheder for hver coin ---
for coin in COINS:
    combined_results = []
    total_polarity = 0
    count = 0

    # Google News
    search_terms = [coin] + EXTRA_TERMS
    for term in search_terms:
        url = GOOGLE_BASE_URL.format(query=term)
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
            for item in items[:5]:
                title = item.title.text
                if title in sent_titles:
                    continue
                sent_titles.add(title)
                description = item.description.text if item.description else ""
                combined_text = f"{title} {description}"
                polarity = TextBlob(combined_text).sentiment.polarity
                total_polarity += polarity
                count += 1
                combined_results.append({"source": "Google News", "title": title, "description": description, "sentiment": polarity})
                if abs(polarity) >= 0.4:
                    alert_messages.append(f"📰 {coin.upper()} ({'Positive' if polarity > 0 else 'Negative'}): {title}\n→ {description.strip()[:150]}...")
        except Exception as e:
            print(f"⚠️ Fejl ved Google News for {term}: {e}")

    # Cointelegraph
    ct_url = COINTELEGRAPH_URLS.get(coin)
    if ct_url:
        try:
            response = requests.get(ct_url)
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
            for item in items[:5]:
                title = item.title.text
                if title in sent_titles:
                    continue
                sent_titles.add(title)
                description = item.description.text if item.description else ""
                combined_text = f"{title} {description}"
                polarity = TextBlob(combined_text).sentiment.polarity
                total_polarity += polarity
                count += 1
                combined_results.append({"source": "Cointelegraph", "title": title, "description": description, "sentiment": polarity})
                if abs(polarity) >= 0.4:
                    alert_messages.append(f"📰 {coin.upper()} ({'Positive' if polarity > 0 else 'Negative'}): {title}\n→ {description.strip()[:150]}...")
        except Exception as e:
            print(f"⚠️ Fejl ved Cointelegraph for {coin}: {e}")

    sentiment_results[coin.upper()] = {
        "average_sentiment": round(total_polarity / count, 3) if count > 0 else 0,
        "articles": combined_results,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }

# --- Makro nyheder ---
macro_results = []
macro_polarity = 0
macro_count = 0
for term in MACRO_TERMS:
    url = GOOGLE_BASE_URL.format(query=term)
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")
        for item in items[:5]:
            title = item.title.text
            if title in sent_titles:
                continue
            sent_titles.add(title)
            description = item.description.text if item.description else ""
            combined_text = f"{title} {description}"
            polarity = TextBlob(combined_text).sentiment.polarity
            macro_polarity += polarity
            macro_count += 1
            macro_results.append({"term": term, "source": "Google News", "title": title, "description": description, "sentiment": polarity})
            if abs(polarity) >= 0.4:
                alert_messages.append(f"🌍 {term.title()} ({'Positive' if polarity > 0 else 'Negative'}): {title}\n→ {description.strip()[:150]}...")
    except Exception as e:
        print(f"⚠️ Fejl ved makroterm '{term}': {e}")

sentiment_results["MACRO"] = {
    "average_sentiment": round(macro_polarity / macro_count, 3) if macro_count > 0 else 0,
    "articles": macro_results,
    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
}

# --- CNBC & TradingView ---
for name, feed_url in ADDITIONAL_FEEDS.items():
    try:
        response = requests.get(feed_url)
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")
        for item in items[:5]:
            title = item.title.text
            if title in sent_titles:
                continue
            sent_titles.add(title)
            description = item.description.text if item.description else ""
            combined_text = f"{title} {description}"
            polarity = TextBlob(combined_text).sentiment.polarity
            if abs(polarity) >= 0.4:
                alert_messages.append(f"📡 {name} ({'Positive' if polarity > 0 else 'Negative'}): {title}\n→ {description.strip()[:150]}...")
    except Exception as e:
        print(f"⚠️ Fejl ved {name}: {e}")

# Save results
with open("news_sentiment.json", "w") as f:
    json.dump(sentiment_results, f, indent=2)

print("✅ Nyhedsdata analyseret og gemt i news_sentiment.json")

if alert_messages:
    alert_text = "\n\n".join(alert_messages)
    for chat_id in CHAT_IDS:
        bot.send_message(chat_id=chat_id.strip(), text=f"🚨 Vigtige nyheder fundet:\n\n{alert_text}")

