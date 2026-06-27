import os
import time
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
X_USERNAMES = os.getenv("X_USERNAMES", "").split(",")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

# RSS sources - dicoba berurutan sampai ada yang berhasil
RSS_SOURCES = [
    "https://rsshub.app/twitter/user/{username}",
    "https://nitter.tiekoetter.com/{username}/rss",
    "https://nitter.poast.org/{username}/rss",
    "https://nitter.privacydev.net/{username}/rss",
    "https://nitter.lucahammer.com/{username}/rss",
    "https://nitter.mint.lgbt/{username}/rss",
    "https://nitter.space/{username}/rss",
    "https://nitter.1d4.us/{username}/rss",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

last_seen = {}


def fetch_rss(username: str):
    for source_template in RSS_SOURCES:
        url = source_template.format(username=username.strip())
        try:
            r = requests.get(url, timeout=15, headers=HEADERS)
            if r.status_code == 200 and "<item>" in r.text:
                log.info(f"Berhasil ambil RSS dari: {url}")
                return r.text, url
            else:
                log.debug(f"Gagal: {url} status={r.status_code}")
        except Exception as e:
            log.debug(f"Error: {url} — {e}")
            continue
    return None, None


def parse_rss(xml_text: str, source_url: str):
    try:
        root = ET.fromstring(xml_text)
        items = root.findall(".//item")
        results = []
        for item in items:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            guid = item.findtext("guid", link).strip()

            # Bersihkan link ke x.com
            clean_link = link
            for domain in ["nitter.tiekoetter.com", "nitter.poast.org", "nitter.privacydev.net",
                           "nitter.lucahammer.com", "nitter.mint.lgbt", "nitter.space", "nitter.1d4.us"]:
                clean_link = clean_link.replace(f"https://{domain}", "https://x.com")

            results.append({"id": guid, "title": title, "link": clean_link})
        return results
    except Exception as e:
        log.error(f"Gagal parse RSS: {e}")
        return []


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            log.error(f"Gagal kirim Telegram: {r.text}")
        else:
            log.info("Notif Telegram berhasil dikirim!")
    except Exception as e:
        log.error(f"Error kirim Telegram: {e}")


def check_feed(username: str):
    xml_text, source_url = fetch_rss(username)
    if not xml_text:
        log.warning(f"Semua RSS source gagal untuk @{username}")
        return

    entries = parse_rss(xml_text, source_url)
    if not entries:
        log.info(f"RSS OK tapi tidak ada item untuk @{username}")
        return

    latest = entries[0]
    tweet_id = latest["id"]

    if username not in last_seen:
        last_seen[username] = tweet_id
        log.info(f"@{username} — inisialisasi OK, memantau tweet baru...")
        return

    if tweet_id == last_seen[username]:
        log.info(f"@{username} — tidak ada tweet baru")
        return

    last_seen[username] = tweet_id
    waktu = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    pesan = (
        f"🔔 <b>Tweet Baru dari @{username}</b>\n\n"
        f"{latest['title']}\n\n"
        f"🔗 <a href='{latest['link']}'>Lihat Tweet</a>\n"
        f"🕐 {waktu}"
    )

    log.info(f"Tweet baru dari @{username}! Mengirim notif...")
    send_telegram(pesan)


def main():
    log.info("🚀 Bot X Notifier mulai jalan...")
    usernames = [u.strip() for u in X_USERNAMES if u.strip()]

    if not usernames:
        log.error("X_USERNAMES belum diset!")
        return

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("TELEGRAM_TOKEN atau TELEGRAM_CHAT_ID belum diset!")
        return

    log.info(f"Memantau: {', '.join(['@' + u for u in usernames])}")
    log.info(f"Interval: {POLL_INTERVAL} detik")

    send_telegram(
        f"✅ <b>Bot X Notifier aktif!</b>\n\n"
        f"Memantau: {', '.join(['@' + u for u in usernames])}\n"
        f"Interval: setiap {POLL_INTERVAL} detik"
    )

    while True:
        for username in usernames:
            try:
                check_feed(username)
            except Exception as e:
                log.error(f"Error saat cek @{username}: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
