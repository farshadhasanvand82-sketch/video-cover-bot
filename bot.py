import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from hydrogram import Client, filters
from hydrogram.types import Message

# --- راه‌اندازی سرور وب کوچک برای جلوگیری از خطای پورت در رندر ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Video Cover Bot is running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# اجرای سرور در پس‌زمینه
threading.Thread(target=run_server, daemon=True).start()
# -------------------------------------------------------------

# تنظیمات اتصال به تلگرام
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BOT_TOKEN = "9002902968:AAG86OED4q23-9lMK7ZbOFbncSi5s7fdTz4"

app = Client(
    "video_cover_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.video | filters.document)
async def process_video(client: Client, message: Message):
    media = message.video or message.document
    if not media:
        return

    status_msg = await message.reply_text("📥 در حال دانلود ویدیو...")
    
    video_path = await client.download_media(message)
    
    await status_msg.edit_text("⚙️ در حال پردازش ویدیو با FFmpeg...")
    
    output_path = f"output_{message.id}.mp4"
    
    cmd = f"ffmpeg -i '{video_path}' -c copy '{output_path}' -y"
    
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    
    await status_msg.edit_text("📤 در حال ارسال ویدیوی نهایی...")
    
    await message.reply_video(
        video=output_path,
        caption="✅ ویدیو با موفقیت پردازش شد."
    )
    
    await status_msg.delete()
    if os.path.exists(video_path):
        os.remove(video_path)
    if os.path.exists(output_path):
        os.remove(output_path)

print("Bot is running...")
app.run()
