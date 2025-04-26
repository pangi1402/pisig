import requests
import schedule
import time
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from io import BytesIO
from telegram import Bot
from flask import Flask
import socket
import threading
import os

# Cấu hình bot Telegram
TOKEN = "7643943023:AAFOUB7PAiT286EarptGwIXTzxHwQfAaPe0"
CHAT_ID = "6982755436"
bot = Bot(token=TOKEN)


# Gửi tín hiệu với biểu đồ và ảnh cover
def send_signal_message(text, fig=None):
    if fig:
        buf = BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        bot.send_photo(chat_id=CHAT_ID, photo=buf, caption=text)
        plt.close(fig)

    # Gửi ảnh nền cover (cover.org)
    if os.path.exists("cover.org"):
        with open("cover.org", "rb") as cover:
            bot.send_photo(
                chat_id=CHAT_ID,
                photo=cover,
                caption=
                "📢 Pi Signal by Pangi – Tín hiệu kỹ thuật & tích lũy crypto!")


# Lấy dữ liệu PI/USDT từ MEXC
def fetch_price_data():
    url = "https://www.mexc.com/open/api/v2/market/kline?symbol=PI_USDT&interval=4h&limit=120"
    try:
        res = requests.get(url)
        if res.status_code != 200:
            print(f"⚠️ API MEXC lỗi: {res.status_code}")
            return [], []
        data = res.json()
        klines = data.get("data", [])
        prices = [float(candle[2]) for candle in klines]
        dates = [
            datetime.fromtimestamp(int(candle[0]) /
                                   1000).strftime("%d/%m %H:%M")
            for candle in klines
        ]
        return prices, dates
    except Exception as e:
        print(f"⚠️ Lỗi khi lấy dữ liệu: {e}")
        return [], []


# Tính SMA và RSI
def calc_sma(data, period=20):
    return [
        sum(data[i - period:i]) / period if i >= period else None
        for i in range(len(data))
    ]


def calc_rsi(data, period=14):
    rsis = []
    for i in range(period, len(data)):
        gains = losses = 0
        for j in range(i - period + 1, i + 1):
            delta = data[j] - data[j - 1]
            if delta > 0:
                gains += delta
            else:
                losses -= delta
        avg_gain = gains / period
        avg_loss = losses / period if losses != 0 else 1e-10
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsis.append(rsi)
    return [None] * period + rsis


# Thêm logo (logo.png) vào biểu đồ
def add_logo(fig, ax):
    logo_path = "logo2.png"
    if os.path.exists(logo_path):
        try:
            logo_img = plt.imread(logo_path)
            imagebox = OffsetImage(logo_img, zoom=0.06)
            ab = AnnotationBbox(imagebox, (0.88, 0.14),
                                xycoords='axes fraction',
                                frameon=False)
            ax.add_artist(ab)
        except Exception as e:
            print(f"⚠️ Không thể chèn logo: {e}")


# Phân tích và gửi tín hiệu
def check_signals():
    print(f"🕒 {datetime.now().strftime('%H:%M:%S')} – Kiểm tra tín hiệu...")
    prices, dates = fetch_price_data()
    if not prices:
        print("⛔ Không có dữ liệu giá.")
        return

    sma20 = calc_sma(prices, 20)
    sma50 = calc_sma(prices, 50)
    rsi = calc_rsi(prices, 14)

    latest_price = prices[-1]
    latest_rsi = rsi[-1]
    latest_sma20 = sma20[-1]
    latest_sma50 = sma50[-1]

    signal = f"""📊 PI/USDT (4H)
Giá: ${latest_price:.4f}
RSI(14): {latest_rsi:.2f}
SMA20: {latest_sma20:.4f}
SMA50: {latest_sma50:.4f}
"""

    if latest_rsi < 30:
        signal += "🔻 RSI < 30 → Quá bán → Có thể cân nhắc mua dần\n"
    elif 45 <= latest_rsi <= 55:
        signal += "📘 RSI ~50 → Tích lũy → Mua dần ít\n"
    elif latest_rsi > 70:
        signal += "⚠️ RSI > 70 → Tránh mua thêm\n"

    if latest_price < latest_sma20 or latest_price < latest_sma50:
        signal += "📉 Giá < SMA → Mua tích lũy ở vùng thấp\n"
    elif latest_rsi > 30 and rsi[-2] < 30 and latest_price > latest_sma20:
        signal += "✅ RSI bật từ <30 & giá vượt SMA → MUA ĐẸP\n"

    # Vẽ biểu đồ
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(dates, prices, label="Giá", linewidth=2)
    ax.plot(dates, sma20, label="SMA20", linestyle="--")
    ax.plot(dates, sma50, label="SMA50", linestyle="-.")
    ax2 = ax.twinx()
    ax2.plot(dates, rsi, label="RSI", color="purple", linestyle="dotted")

    ax.set_xlabel("Thời gian (4H)")
    ax.set_ylabel("Giá")
    ax2.set_ylabel("RSI")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left")
    ax2.legend(loc="upper right")
    ax.set_xticks(dates[::8])
    ax.tick_params(axis="x", rotation=45)
    fig.suptitle("Biểu đồ PI/USDT - 4H (Giá, RSI, SMA)", fontsize=12)
    fig.tight_layout()

    add_logo(fig, ax)
    send_signal_message(signal, fig)
    print("📨 Đã gửi tín hiệu về Telegram")


# Lịch gửi (UTC)
schedule.every().day.at("02:00").do(check_signals)  # 09:00 VN
schedule.every().day.at("05:00").do(check_signals)  # 12:00 VN
schedule.every().day.at("10:00").do(check_signals)  # 17:00 VN
schedule.every().day.at("16:30").do(check_signals)  # 23:30 VN

# Flask giữ sống bot
app = Flask(__name__)


@app.route("/")
def home():
    return "Pi Bot is running."


# In địa chỉ nếu cần
def print_server_url():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        print(f"🌐 Server nội bộ: http://{ip}:8080")
    except:
        pass


# Lặp schedule
def run_loop():
    while True:
        schedule.run_pending()
        time.sleep(60)


check_signals()
print_server_url()
threading.Thread(target=run_loop).start()
app.run(host="0.0.0.0", port=8080)
