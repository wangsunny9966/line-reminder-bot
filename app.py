import os
import json
import threading
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent
)
import schedule
import time
import pytz

app = Flask(__name__)

# 從環境變數讀取 LINE 設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
USER_ID = os.environ.get('LINE_USER_ID', '')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 台灣時區
TZ = pytz.timezone('Asia/Taipei')

# 提醒資料檔案
REMINDERS_FILE = 'reminders.json'

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return get_default_reminders()

def save_reminders(reminders):
    with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def get_default_reminders():
    return [
        {"time": "07:00", "message": "☀️ 早安！新的一天開始了，記得吃早餐！"},
        {"time": "08:30", "message": "🏢 準備上班囉！記得帶鑰匙、手機、錢包。"},
        {"time": "12:00", "message": "🍱 午餐時間到！記得好好吃飯，補充能量。"},
        {"time": "14:00", "message": "☕ 下午精神來一杯，繼續加油！"},
        {"time": "18:00", "message": "🏠 下班時間！記得記帳今天的花費。"},
        {"time": "21:00", "message": "📒 睡前提醒：記帳了嗎？明天行程確認了嗎？"},
        {"time": "22:30", "message": "😴 該準備睡覺了，明天也要加油！"},
    ]

def send_reminder(message):
    if USER_ID:
        try:
            line_bot_api.push_message(USER_ID, TextSendMessage(text=message))
        except Exception as e:
            print(f"發送失敗: {e}")

def setup_schedule():
    schedule.clear()
    reminders = load_reminders()
    for r in reminders:
        t = r['time']
        msg = r['message']
        schedule.every().day.at(t).do(send_reminder, message=msg)
    print(f"已設定 {len(reminders)} 個提醒")

def run_schedule():
    setup_schedule()
    while True:
        schedule.run_pending()
        time.sleep(30)

def format_reminders(reminders):
    lines = ["📋 *目前的提醒清單*\n"]
    for i, r in enumerate(reminders, 1):
        lines.append(f"{i}. {r['time']} - {r['message']}")
    lines.append("\n💡 指令說明：")
    lines.append("• 新增 HH:MM 內容 → 新增提醒")
    lines.append("• 刪除 編號 → 刪除提醒")
    lines.append("• 清單 → 查看所有提醒")
    lines.append("• 說明 → 查看指令")
    return "\n".join(lines)

def help_message():
    return (
        "🤖 *提醒機器人指令*\n\n"
        "📋 查看清單：\n輸入「清單」\n\n"
        "➕ 新增提醒：\n輸入「新增 08:30 開會」\n\n"
        "❌ 刪除提醒：\n輸入「刪除 3」（刪除第3項）\n\n"
        "🔄 重設預設：\n輸入「重設」\n\n"
        "📌 範例：\n"
        "新增 09:00 記得開晨會\n"
        "新增 20:00 記帳今天花費"
    )

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    welcome = (
        "👋 哈囉！我是你的每日提醒機器人！\n\n"
        "我會在設定的時間自動傳訊息提醒你各種事項。\n\n"
        "輸入「說明」查看所有功能\n"
        "輸入「清單」查看目前提醒"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    reminders = load_reminders()

    if text in ['清單', '列表', '提醒清單']:
        reply = format_reminders(reminders)

    elif text in ['說明', '幫助', 'help', '指令']:
        reply = help_message()

    elif text == '重設':
        reminders = get_default_reminders()
        save_reminders(reminders)
        setup_schedule()
        reply = "✅ 已重設為預設提醒清單！"

    elif text.startswith('新增 ') or text.startswith('新增　'):
        parts = text[3:].strip().split(' ', 1)
        if len(parts) == 2:
            t, msg = parts
            # 驗證時間格式
            try:
                datetime.strptime(t, '%H:%M')
                reminders.append({"time": t, "message": msg})
                reminders.sort(key=lambda x: x['time'])
                save_reminders(reminders)
                setup_schedule()
                reply = f"✅ 已新增提醒：\n{t} - {msg}"
            except ValueError:
                reply = "❌ 時間格式錯誤，請用 HH:MM 格式\n例如：新增 09:30 開會"
        else:
            reply = "❌ 格式錯誤\n請用：新增 08:30 要開會"

    elif text.startswith('刪除 ') or text.startswith('刪除　'):
        num_str = text[3:].strip()
        try:
            num = int(num_str)
            if 1 <= num <= len(reminders):
                removed = reminders.pop(num - 1)
                save_reminders(reminders)
                setup_schedule()
                reply = f"✅ 已刪除第 {num} 項：\n{removed['time']} - {removed['message']}"
            else:
                reply = f"❌ 編號錯誤，目前有 {len(reminders)} 項提醒"
        except ValueError:
            reply = "❌ 請輸入數字，例如：刪除 3"

    else:
        reply = "我收到你的訊息了！\n輸入「說明」查看所有指令 😊"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@app.route("/")
def index():
    return "LINE 提醒機器人運作中 ✅"

@app.route("/send-test", methods=['GET'])
def send_test():
    send_reminder("🧪 測試訊息：機器人運作正常！")
    return "已發送測試訊息"

if __name__ == "__main__":
    # 啟動排程執行緒
    t = threading.Thread(target=run_schedule, daemon=True)
    t.start()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
