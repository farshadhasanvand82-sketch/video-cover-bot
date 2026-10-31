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
        self.wfile.write(b"ZEUC TV Video Bot is running!")

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

# حافظه موقت برای مدیریت مراحل کاربران
user_data = {}

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {}
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 ادیت ویدیو", callback_data="menu_edit")],
        [InlineKeyboardButton("🖼️ بخش کاور ویدیو", callback_data="menu_cover")],
        [InlineKeyboardButton("ℹ️ درباره ربات", callback_data="menu_about")]
    ])
    await message.reply_text(
        "سلام! 👋 به ربات پردازش و مدیریت ویدیو خوش آمدید.\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=keyboard
    )

@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if user_id not in user_data:
        user_data[user_id] = {}

    if data == "menu_edit":
        user_data[user_id]["mode"] = "edit"
        await callback_query.message.edit_text(
            "🛠️ **بخش ادیت ویدیو**\n\nلطفاً ویدیوی خود را بفرستید:"
        )
    elif data == "menu_cover":
        user_data[user_id]["mode"] = "cover_video"
        await callback_query.message.edit_text(
            "🖼️ **بخش کاور ویدیو**\n\nمرحله اول: لطفاً **ویدیو**ی خود را ارسال کنید:"
        )
    elif data == "menu_about":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_main")]
        ])
        await callback_query.message.edit_text(
            "ℹ️ این ربات مجهز به سیستم پردازش FFmpeg و نمایش درصد پیشرفت است.",
            reply_markup=keyboard
        )
    elif data == "back_to_main":
        user_data[user_id] = {}
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 ادیت ویدیو", callback_data="menu_edit")],
            [InlineKeyboardButton("🖼️ بخش کاور ویدیو", callback_data="menu_cover")],
            [InlineKeyboardButton("ℹ️ درباره ربات", callback_data="menu_about")]
        ])
        await callback_query.message.edit_text(
            "به منوی اصلی برگشتیم. لطفاً یک گزینه انتخاب کنید:",
            reply_markup=keyboard
        )

# نمایش درصد پیشرفت
def progress(current, total, message, text):
    now = time.time()
    if hasattr(progress, "last_time") and now - progress.last_time < 2:
        return
    progress.last_time = now

    percentage = current * 100 / total
    speed = current / (now - getattr(progress, "start_time", now)) if now != getattr(progress, "start_time", now) else 0
    
    current_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    speed_mb = speed / (1024 * 1024)

    progress_bar = "█" * int(percentage // 10) + "░" * (10 - int(percentage // 10))
    
    try:
        message.edit_text(
            f"{text}\n\n"
            f"[{progress_bar}] {percentage:.1f}%\n\n"
            f"📊 حجم: {current_mb:.1f} MB از {total_mb:.1f} MB\n"
            f"⚡ سرعت: {speed_mb:.1f} MB/s"
        )
    except Exception:
        pass

# مدیریت دریافت ویدیو و عکس
@app.on_message(filters.video | filters.document | filters.photo)
async def media_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    
    mode = user_data[user_id].get("mode")

    if not mode:
        await message.reply_text("⚠️ لطفاً ابتدا با دستور /start منوی اصلی را باز کنید.")
        return

    # حالت اول: دریافت ویدیو برای گذاشتن کاور
    if mode == "cover_video" and (message.video or message.document):
        status_msg = await message.reply_text("📥 در حال دانلود ویدیو...")
        progress.start_time = time.time()
        
        video_path = await client.download_media(
            message,
            progress=progress,
            progress_args=(status_msg, "📥 **در حال دانلود ویدیو:**")
        )
        
        user_data[user_id]["video_path"] = video_path
        user_data[user_id]["mode"] = "cover_photo"
        
        await status_msg.edit_text("✅ ویدیو با موفقیت دریافت شد!\n\n🖼️ حالا مرحله دوم: لطفاً **عکس کاور** مورد نظرتان را بفرستید.")
        return

    # حالت دوم: دریافت عکس کاور بعد از ویدیو
    elif mode == "cover_photo" and message.photo:
        status_msg = await message.reply_text("📥 در حال دریافت عکس کاور...")
        photo_path = await client.download_media(message)
        
        video_path = user_data[user_id].get("video_path")
        output_path = f"output_{message.id}.mp4"
        
        await status_msg.edit_text("⚙️ در حال الصاق کاور روی ویدیو با FFmpeg...")
        
        # دستور FFmpeg برای چسباندن کاور روی ویدیو
        cmd = f"ffmpeg -i '{video_path}' -i '{photo_path}' -map 0 -map 1 -c copy -disposition:v:1 attached_pic '{output_path}' -y"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        await status_msg.edit_text("📤 در حال آپلود ویدیوی نهایی با کاور جدید...")
        progress.start_time = time.time()
        
        await message.reply_video(
            video=output_path,
            thumb=photo_path,
            caption="✅ کاور با موفقیت روی ویدیو قرار گرفت و پردازش شد.",
            progress=progress,
            progress_args=(status_msg, "📤 **در حال آپلود ویدیوی نهایی:**")
        )
        
        await status_msg.delete()
        
        # پاکسازی فایل‌ها
        for p in [video_path, photo_path, output_path]:
            if p and os.path.exists(p):
                os.remove(p)
        user_data[user_id] = {}
        return

    # حالت سوم: ادیت معمولی ویدیو
    elif mode == "edit" and (message.video or message.document):
        status_msg = await message.reply_text("📥 در حال دانلود ویدیو...")
        progress.start_time = time.time()
        
        video_path = await client.download_media(
            message,
            progress=progress,
            progress_args=(status_msg, "📥 **در حال دانلود ویدیو:**")
        )
        
        await status_msg.edit_text("⚙️ در حال پردازش ویدیو...")
        output_path = f"output_{message.id}.mp4"
        
        cmd = f"ffmpeg -i '{video_path}' -c copy '{output_path}' -y"
        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        
        await status_msg.edit_text("📤 در حال آپلود...")
        progress.start_time = time.time()
        
        await message.reply_video(
            video=output_path,
            caption="✅ ادیت ویدیو با موفقیت انجام شد.",
            progress=progress,
            progress_args=(status_msg, "📤 **در حال آپلود ویدیوی نهایی:**")
        )
        
        await status_msg.delete()
        if os.path.exists(video_path): os.remove(video_path)
        if os.path.exists(output_path): os.remove(output_path)
        user_data[user_id] = {}
        return

print("Bot is running with Cover and Progress features...")
app.run()
