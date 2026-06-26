import os
import time
import logging
import feedparser
import requests
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
X_USERNAMES = os.getenv("X_USERNAMES", "").split(",")  # bisa multiple akun, pisah koma
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))  # detik

# Nitter instances (fallback otomatis kalau satu down)
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
    "https://nitter.tiekoetter.com",
    "https://nitter.space",
    "https://nitter.mint.lgbt",
    "https://nitter.lucahammer.com",
    "https://nitter.pussthecat.org",
]
# Simpan tweet ID terakhir per username
last_seen = {}


def get_rss_url(username: str) -> str:
    for instance in NITTER_INSTANCES:
        url = f"{instance}/{username.strip()}/rss"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                log.info(f"Pakai instance: {instance} untuk @{username}")
                return url
        except Exception:
            continue
    return None


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
    except Exception as e:
        log.error(f"Error kirim Telegram: {e}")


def check_feed(username: str):
    rss_url = get_rss_url(username)
    if not rss_url:
        log.warning(f"Semua Nitter instance gagal untuk @{username}")
        return

    feed = feedparser.parse(rss_url)
    if not feed.entries:
        log.info(f"Tidak ada tweet ditemukan untuk @{username}")
        return

    latest = feed.entries[0]
    tweet_id = latest.get("id", latest.get("link", ""))

    if username not in last_seen:
        # Pertama kali jalan — simpan ID terbaru, jangan kirim notif
        last_seen[username] = tweet_id
        log.info(f"@{username} — inisialisasi, tweet terbaru: {tweet_id}")
        return

    if tweet_id == last_seen[username]:
        log.info(f"@{username} — tidak ada tweet baru")
        return

    # Ada tweet baru!
    last_seen[username] = tweet_id
    title = latest.get("title", "")
    link = latest.get("link", "").replace(
        next((i for i in NITTER_INSTANCES if i in latest.get("link", "")), NITTER_INSTANCES[0]),
        "https://x.com"
    )

    # Bersihkan link agar ke x.com bukan nitter
    for ni in NITTER_INSTANCES:
        link = link.replace(ni, "https://x.com")

    waktu = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    pesan = (
        f"🔔 <b>Tweet Baru dari @{username}</b>\n\n"
        f"{title}\n\n"
        f"🔗 <a href='{link}'>Lihat Tweet</a>\n"
        f"🕐 {waktu}"
    )

    log.info(f"Tweet baru dari @{username}! Mengirim notif...")
    send_telegram(pesan)


def main():
    log.info("🚀 Bot X Notifier mulai jalan...")
    usernames = [u.strip() for u in X_USERNAMES if u.strip()]

    if not usernames:
        log.error("Tidak ada username X yang diset di X_USERNAMES!")
        return

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("TELEGRAM_TOKEN atau TELEGRAM_CHAT_ID belum diset!")
        return

    log.info(f"Memantau akun: {', '.join(['@' + u for u in usernames])}")
    log.info(f"Interval polling: {POLL_INTERVAL} detik")

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
