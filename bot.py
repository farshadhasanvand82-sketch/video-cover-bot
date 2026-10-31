import os
import asyncio
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- راه‌اندازی سرور وب کوچک برای رندر ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ZEUC TV Cover Bot is running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()
# ----------------------------------------

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BOT_TOKEN = "9238834032:AAFl0JBdvFrDR2AFeoHH7TIFvOGw2jNCxM0"

app = Client(
    "video_cover_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# حافظه موقت برای ذخیره اطلاعات ویدیو، کاور و وضعیت کاربران
user_data = {}

# تابع نمایش درصد پیشرفت زنده
def progress(current, total, message, text):
    if total == 0:
        return
    now = time.time()
    if hasattr(progress, "last_time") and now - progress.last_time < 1.5:
        return
    progress.last_time = now

    percentage = current * 100 / total
    elapsed = now - getattr(progress, "start_time", now)
    speed = current / elapsed if elapsed > 0 else 0
    
    current_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    speed_mb = speed / (1024 * 1024)

    filled = int(percentage // 10)
    progress_bar = "█" * filled + "░" * (10 - filled)
    
    txt = (
        f"{text}\n\n"
        f"[{progress_bar}] {percentage:.1f}%\n\n"
        f"📊 حجم: {current_mb:.1f} MB از {total_mb:.1f} MB\n"
        f"⚡ سرعت: {speed_mb:.1f} MB/s"
    )
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(message.edit_text(txt))
    except Exception:
        pass

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {"mode": "waiting_for_video"}
    
    await message.reply_text(
        "سلام! 👋 به ربات پردازش ویدیو و کاور خوش آمدید.\n\n"
        "مرحله اول: لطفاً **ویدیو**ی خود را ارسال کنید:"
    )

@app.on_message(filters.video | filters.document | filters.photo)
async def media_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"mode": "waiting_for_video"}
    
    state = user_data[user_id].get("mode")

    # ۱. دریافت ویدیو
    if state == "waiting_for_video" and (message.video or message.document):
        status_msg = await message.reply_text("📥 در حال آماده‌سازی برای دانلود ویدیو...")
        progress.start_time = time.time()
        
        video_path = await client.download_media(
            message,
            progress=progress,
            progress_args=(status_msg, "📥 **در حال دانلود ویدیو:**")
        )
        
        user_data[user_id]["video_path"] = video_path
        user_data[user_id]["mode"] = "waiting_for_photo"
        
        await status_msg.edit_text("✅ ویدیو دریافت شد!\n\n🖼️ مرحله دوم: لطفاً **عکس کاور** مورد نظرتان را بفرستید.")
        return

    # ۲. دریافت عکس کاور
    elif state == "waiting_for_photo" and message.photo:
        status_msg = await message.reply_text("📥 در حال دریافت عکس کاور...")
        photo_path = await client.download_media(message)
        
        user_data[user_id]["photo_path"] = photo_path
        user_data[user_id]["mode"] = "waiting_for_quality"
        
        # نمایش منوی انتخاب کیفیت
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("360p", callback_data="quality_360"), InlineKeyboardButton("480p", callback_data="quality_480")],
            [InlineKeyboardButton("720p", callback_data="quality_720"), InlineKeyboardButton("1080p", callback_data="quality_1080")],
            [InlineKeyboardButton("⚙️ کیفیت اصلی (بدون تغییر اندازه)", callback_data="quality_original")]
        ])
        
        await status_msg.edit_text(
            "✅ کاور دریافت شد!\n\n"
            "🎚️ مرحله سوم: لطفاً کیفیت خروجی ویدیو را انتخاب کنید:",
            reply_markup=keyboard
        )
        return

    else:
        await message.reply_text("⚠️ لطفاً طبق مراحل پیش بروید. برای شروع /start را بزنید.")

# ۳. مدیریت دکمه‌های انتخاب کیفیت و پردازش نهایی با FFmpeg
@app.on_callback_query()
async def quality_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if user_id not in user_data or user_data[user_id].get("mode") != "waiting_for_quality":
        await callback_query.answer("⚠️ لطفاً ابتدا ویدیو و کاور را ارسال کنید.", show_alert=True)
        return

    await callback_query.answer()
    status_msg = callback_query.message
    
    video_path = user_data[user_id].get("video_path")
    photo_path = user_data[user_id].get("photo_path")
    output_path = f"output_{user_id}.mp4"

    # تعیین فیلتر مقیاس (Scale) بر اساس کیفیت انتخابی
    scale_filter = ""
    if data == "quality_360":
        scale_filter = "scale=-2:360"
    elif data == "quality_480":
        scale_filter = "scale=-2:480"
    elif data == "quality_720":
        scale_filter = "scale=-2:720"
    elif data == "quality_1080":
        scale_filter = "scale=-2:1080"
    else:
        scale_filter = "copy" # کیفیت اصلی

    await status_msg.edit_text("⚙️ در حال الصاق کاور و تغییر کیفیت با FFmpeg...")

    # دستور FFmpeg برای چسباندن کاور و تغییر رزولوشن ویدیو
    if scale_filter == "copy":
        cmd = f"ffmpeg -i '{video_path}' -i '{photo_path}' -map 0 -map 1 -c copy -disposition:v:1 attached_pic '{output_path}' -y"
    else:
        cmd = f"ffmpeg -i '{video_path}' -i '{photo_path}' -filter:v:0 '{scale_filter}' -map 0:v -map 0:a? -map 1:v -c:v:0 libx264 -c:a copy -c:v:1 copy -disposition:v:1 attached_pic '{output_path}' -y"

    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()

    await status_msg.edit_text("📤 در حال آماده‌سازی برای آپلود ویدیوی نهایی...")
    progress.start_time = time.time()

    await client.send_video(
        chat_id=user_id,
        video=output_path,
        thumb=photo_path,
        caption="✅ ویدیو با موفقیت پردازش شد و کاور و کیفیت جدید روی آن اعمال گردید.",
        progress=progress,
        progress_args=(status_msg, "📤 **در حال آپلود ویدیوی نهایی:**")
    )

    await status_msg.delete()

    # پاکسازی فایل‌ها از روی هاست رندر درجا
    for p in [video_path, photo_path, output_path]:
        if p and os.path.exists(p):
            os.remove(p)

    user_data[user_id] = {"mode": "waiting_for_video"}

print("Bot is running with Cover, Quality selection, and Live Progress...")
app.run()
