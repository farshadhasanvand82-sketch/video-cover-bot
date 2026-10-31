import os
import asyncio
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from hydrogram.errors import UserNotParticipant

# --- راه‌اندازی سرور وب کوچک برای رندر ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ZEUC TV Bot is running!")

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

ADMINS = {8886868325, 8250289921}

users_db = {}     # ذخیره مشخصات کاربران: {user_id: {"name": ..., "username": ...}}
user_traffic = {} # حجم کاربران
settings = {"forced_channel": None}
user_data = {}

# کیبورد دائمی پایین صفحه
main_reply_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🎬 شروع پردازش (کاور + ویدیو)"), KeyboardButton("👤 حساب من")],
        [KeyboardButton("🛒 خرید اشتراک"), KeyboardButton("ℹ️ راهنما")]
    ],
    resize_keyboard=True
)

def create_progress_callback(message, text):
    start_time = time.time()
    last_update_time = [0]

    async def progress_callback(current, total):
        if total == 0:
            return
        now = time.time()
        if now - last_update_time[0] < 1.5:
            return
        last_update_time[0] = now

        percentage = current * 100 / total
        elapsed = now - start_time
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
            await message.edit_text(txt)
        except Exception:
            pass

    return progress_callback

async def check_forced_sub(client, message):
    channel = settings.get("forced_channel")
    if not channel:
        return True
    try:
        user_id = message.from_user.id
        if user_id in ADMINS:
            return True
        await client.get_chat_member(channel, user_id)
        return True
    except UserNotParticipant:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 عضویت در کانال ربات", url=f"https://t.me/{channel.replace('@', '')}")],
            [InlineKeyboardButton("🔄 بررسی مجدد عضویت", callback_data="check_membership")]
        ])
        await message.reply_text("⚠️ لطفاً ابتدا در کانال زیر عضو شوید:", reply_markup=keyboard)
        return False
    except Exception:
        return True

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    
    # ثبت نام، اسم و یوزرنیم کاربر
    name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    username = f"@{message.from_user.username}" if message.from_user.username else "ندارد"
    
    users_db[user_id] = {"name": name if name else "بدون نام", "username": username}
    
    if user_id not in user_traffic and user_id not in ADMINS:
        user_traffic[user_id] = 500.0

    user_data[user_id] = {"mode": "main_menu"}
    
    if not await check_forced_sub(client, message):
        return

    remaining = "نامحدود (ادمین)" if user_id in ADMINS else f"{user_traffic.get(user_id, 0):.1f} مگابایت"

    await message.reply_text(
        f"سلام! 👋 به ربات مدیریت ویدیو خوش آمدید.\n\n"
        f"🎁 حجم هدیه تست شما: **{remaining}**\n\n"
        "از دکمه‌های پایین صفحه استفاده کنید:",
        reply_markup=main_reply_keyboard
    )

@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    message = callback_query.message

    if data == "check_membership":
        if await check_forced_sub(client, message):
            await message.edit_text("✅ عضویت تایید شد! دکمه شروع را بزنید.")
        else:
            await callback_query.answer("⚠️ هنوز عضو نشده‌اید!", show_alert=True)
        return

    if data == "start_process" or data == "cancel":
        if user_id not in ADMINS and user_traffic.get(user_id, 0) <= 0:
            await message.reply_text("❌ حجم تست شما تمام شده است. خرید اشتراک: @izeucs")
            return

        user_data[user_id] = {"mode": "waiting_for_photo"}
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel")]])
        await message.reply_text("🖼️ **مرحله اول:** لطفاً **عکس کاور** مورد نظرتان را ارسال کنید:", reply_markup=keyboard)

    elif data == "admin_panel" and user_id in ADMINS:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 آمار و لیست کاربران", callback_data="admin_user_list")],
            [InlineKeyboardButton("⭐ شارژ حجم کاربر", callback_data="admin_set_sub")],
            [InlineKeyboardButton("🔙 بستن پنل", callback_data="cancel")]
        ])
        await message.edit_text("⚙️ **پنل مدیریت ادمین:**", reply_markup=keyboard)

    elif data == "admin_user_list" and user_id in ADMINS:
        if not users_db:
            await callback_query.answer("هنوز کاربری ثبت نشده است.", show_alert=True)
            return
        
        text = f"📊 **لیست کل کاربران ({len(users_db)} نفر):**\n\n"
        for uid, info in users_db.items():
            text += f"👤 نام: {info['name']}\n🆔 آیدی عددی: `{uid}`\n🔗 یوزرنیم: {info['username']}\n-------------------\n"
            
        # اگر لیست خیلی بلند بود، به بخش‌های کوچک‌تر تقسیم می‌کنیم یا ارسال می‌کنیم
        if len(text) > 4000:
            text = text[:4000] + "\n\n... (لیست طولانی است)"
            
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]])
        await message.edit_text(text, reply_markup=keyboard)

    elif data == "admin_set_sub" and user_id in ADMINS:
        user_data[user_id]["mode"] = "waiting_for_sub_info"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]])
        await message.edit_text("⭐ فرمت شارژ حجم:\n`USER_ID MB`\nمثال:\n`123456789 1000`", reply_markup=keyboard)

    elif data.startswith("quality_"):
        if user_id not in user_data or user_data[user_id].get("mode") != "waiting_for_quality":
            await callback_query.answer("⚠️ لطفاً مراحل را طی کنید.", show_alert=True)
            return

        await callback_query.answer()
        status_msg = await message.reply_text("⚙️ در حال پردازش ویدیو با FFmpeg...")
        
        video_path = user_data[user_id].get("video_path")
        photo_path = user_data[user_id].get("photo_path")
        output_path = f"output_{user_id}.mp4"

        scale_filter = ""
        if data == "quality_360": scale_filter = "scale=-2:360"
        elif data == "quality_480": scale_filter = "scale=-2:480"
        elif data == "quality_720": scale_filter = "scale=-2:720"
        elif data == "quality_1080": scale_filter = "scale=-2:1080"
        else: scale_filter = "copy"

        if scale_filter == "copy":
            cmd = f"ffmpeg -i '{video_path}' -i '{photo_path}' -map 0 -map 1 -c copy -disposition:v:1 attached_pic -movflags +faststart '{output_path}' -y"
        else:
            cmd = f"ffmpeg -i '{video_path}' -i '{photo_path}' -vf '{scale_filter}' -c:v libx264 -preset ultrafast -crf 28 -c:a copy -c:v:1 copy -disposition:v:1 attached_pic -movflags +faststart '{output_path}' -y"

        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()

        await status_msg.edit_text("📤 در حال آپلود ویدیوی نهایی...")
        prog_func = create_progress_callback(status_msg, "📤 **در حال آپلود ویدیوی نهایی:**")

        await client.send_video(
            chat_id=user_id,
            video=output_path,
            thumb=photo_path,
            caption="✅ ویدیو با موفقیت پردازش شد.",
            progress=prog_func
        )

        await status_msg.delete()

        for p in [video_path, photo_path, output_path]:
            if p and os.path.exists(p):
                os.remove(p)

        user_data[user_id] = {"mode": "main_menu"}

@app.on_message(filters.text | filters.video | filters.document | filters.photo)
async def media_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text
    
    # ثبت خودکار اطلاعات کاربر در صورت ارسال پیام
    name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    username = f"@{message.from_user.username}" if message.from_user.username else "ندارد"
    if user_id not in users_db:
        users_db[user_id] = {"name": name if name else "بدون نام", "username": username}

    if user_id not in user_data:
        user_data[user_id] = {"mode": "main_menu"}
    
    state = user_data[user_id].get("mode")

    # مدیریت کلیک روی دکمه‌های پایین صفحه (Reply Keyboard)
    if text == "🎬 شروع پردازش (کاور + ویدیو)":
        if user_id not in ADMINS and user_traffic.get(user_id, 0) <= 0:
            await message.reply_text("❌ حجم تست شما تمام شده است. خرید اشتراک: @izeucs")
            return
        user_data[user_id] = {"mode": "waiting_for_photo"}
        await message.reply_text("🖼️ **مرحله اول:** لطفاً **عکس کاور** مورد نظرتان را ارسال کنید:")
        return

    elif text == "👤 حساب من":
        remaining = "نامحدود (ادمین)" if user_id in ADMINS else f"{user_traffic.get(user_id, 0):.1f} مگابایت"
        await message.reply_text(f"👤 حساب کاربری:\n🆔 شناسه: `{user_id}`\n📊 حجم باقی‌مانده: **{remaining}**")
        return

    elif text == "🛒 خرید اشتراک":
        await message.reply_text("🛒 برای خرید اشتراک و افزایش حجم، به پشتیبانی پیام دهید:\n👉 @izeucs")
        return

    elif text == "ℹ️ راهنما":
        await message.reply_text("ℹ️ این ربات برای قرار دادن کاور روی ویدیو و تغییر کیفیت طراحی شده است. از دکمه‌ها استفاده کنید.")
        return

    # دستور پنل ادمین
    if user_id in ADMINS and text == "/admin":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 آمار و لیست کاربران", callback_data="admin_user_list")],
            [InlineKeyboardButton("⭐ شارژ حجم کاربر", callback_data="admin_set_sub")],
            [InlineKeyboardButton("🔙 بستن", callback_data="cancel")]
        ])
        await message.reply_text("⚙️ **پنل مدیریت ادمین:**", reply_markup=keyboard)
        return

    # شارژ حجم توسط ادمین
    if user_id in ADMINS and state == "waiting_for_sub_info":
        try:
            parts = text.strip().split()
            target_user = int(parts[0])
            added_mb = float(parts[1])
            user_traffic[target_user] = user_traffic.get(target_user, 0) + added_mb
            user_data[user_id]["mode"] = "main_menu"
            await message.reply_text(f"✅ مبلغ {added_mb} MB به کاربر `{target_user}` اضافه شد.")
            await client.send_message(target_user, f"⭐ حساب شما شارژ شد: {added_mb} MB")
        except Exception:
            await message.reply_text("❌ فرمت اشتباه است. مثال: `123456789 1000`")
        return

    # ۱. دریافت کاور
    if state == "waiting_for_photo" and message.photo:
        status_msg = await message.reply_text("📥 در حال دریافت عکس کاور...")
        photo_path = await client.download_media(message)
        
        user_data[user_id]["photo_path"] = photo_path
        user_data[user_id]["mode"] = "waiting_for_video"
        
        await status_msg.edit_text("✅ کاور دریافت شد!\n\n🎬 **مرحله دوم:** حالا **ویدیو** را بفرستید:")
        return

    # ۲. دریافت ویدیو
    elif state == "waiting_for_video" and (message.video or message.document):
        if not await check_forced_sub(client, message):
            return
            
        media_size_mb = (message.video.file_size if message.video else message.document.file_size) / (1024 * 1024)
        
        if user_id not in ADMINS:
            if user_traffic.get(user_id, 0) < media_size_mb:
                await message.reply_text(f"❌ حجم ویدیو ({media_size_mb:.1f} MB) از اعتبار شما بیشتر است!\nخرید: @izeucs")
                return
            user_traffic[user_id] -= media_size_mb

        status_msg = await message.reply_text("📥 در حال دانلود ویدیو...")
        prog_func = create_progress_callback(status_msg, "📥 **در حال دانلود ویدیو:**")
        
        video_path = await client.download_media(message, progress=prog_func)
        
        user_data[user_id]["video_path"] = video_path
        user_data[user_id]["mode"] = "waiting_for_quality"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("360p", callback_data="quality_360"), InlineKeyboardButton("480p", callback_data="quality_480")],
            [InlineKeyboardButton("720p", callback_data="quality_720"), InlineKeyboardButton("1080p", callback_data="quality_1080")],
            [InlineKeyboardButton("⚙️ کیفیت اصلی", callback_data="quality_original")]
        ])
        
        await status_msg.edit_text("✅ ویدیو دانلود شد!\n\n🎚️ **مرحله سوم:** کیفیت خروجی را انتخاب کنید:", reply_markup=keyboard)
        return

    elif state == "main_menu":
        await message.reply_text("⚠️ لطفاً از دکمه‌های پایین صفحه استفاده کنید:", reply_markup=main_reply_keyboard)

print("Bot is running with Admin User List feature...")
app.run()
