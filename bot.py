import os
import asyncio
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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

# ادمین‌های ربات
ADMINS = {8886868325, 8250289921}

users_db = set()
user_traffic = {}  # حجم کاربران بر حسب مگابایت
settings = {"forced_channel": None}
user_data = {}

# تابع پیشرفته نمایش درصد پیشرفت زنده
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

# بررسی قفل کانال اجباری
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
        await message.reply_text(
            "⚠️ برای استفاده از ربات، لطفاً ابتدا در کانال زیر عضو شوید و سپس روی بررسی مجدد کلیک کنید:",
            reply_markup=keyboard
        )
        return False
    except Exception:
        return True

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    users_db.add(user_id)
    
    if user_id not in user_traffic and user_id not in ADMINS:
        user_traffic[user_id] = 200.0  # ۲۰۰ مگابایت هدیه تست اولیه

    user_data[user_id] = {"mode": "main_menu"}
    
    if not await check_forced_sub(client, message):
        return

    remaining = "نامحدود (ادمین)" if user_id in ADMINS else f"{user_traffic.get(user_id, 0):.1f} مگابایت"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 شروع پردازش (اول کاور، بعد ویدیو)", callback_data="start_process")],
        [InlineKeyboardButton("👤 حساب کاربری و حجم من", callback_data="user_account")],
        [InlineKeyboardButton("🛒 خرید اشتراک", url="https://t.me/izeucs")],
        [InlineKeyboardButton("ℹ️ درباره ما", callback_data="about_bot")]
    ])
    
    if user_id in ADMINS:
        keyboard.inline_keyboard.append([InlineKeyboardButton("⚙️ پنل مدیریت ادمین", callback_data="admin_panel")])

    await message.reply_text(
        f"سلام! 👋 به ربات هوشمند مدیریت ویدیو خوش آمدید.\n\n"
        f"🎁 حجم هدیه تست شما: **{remaining}**\n\n"
        "لطفاً از طریق دکمه‌های شیشه‌ای زیر گزینه مورد نظر را انتخاب کنید:",
        reply_markup=keyboard
    )

@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    message = callback_query.message

    if data == "check_membership":
        if await check_forced_sub(client, message):
            await message.edit_text("✅ عضویت شما تایید شد! حالا /start را ارسال کنید.")
        else:
            await callback_query.answer("⚠️ هنوز در کانال عضو نشده‌اید!", show_alert=True)
        return

    if data == "start_process":
        if user_id not in ADMINS and user_traffic.get(user_id, 0) <= 0:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 خرید اشتراک از @izeucs", url="https://t.me/izeucs")],
                [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_home")]
            ])
            await message.edit_text(
                "❌ حجم تست رایگان شما به پایان رسیده است!\n\n"
                "برای تهیه اشتراک به پشتیبانی پیام دهید:",
                reply_markup=keyboard
            )
            return

        # تغییر ترتیب: اول گرفتن عکس کاور
        user_data[user_id] = {"mode": "waiting_for_photo"}
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو و بازگشت", callback_data="back_home")]])
        await message.edit_text(
            "🖼️ **مرحله اول:** لطفاً ابتدا **عکس کاور** مورد نظرتان را بفرستید:",
            reply_markup=keyboard
        )

    elif data == "user_account":
        remaining = "نامحدود (ادمین)" if user_id in ADMINS else f"{user_traffic.get(user_id, 0):.1f} مگابایت"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 خرید اشتراک", url="https://t.me/izeucs")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_home")]
        ])
        await message.edit_text(
            f"👤 **اطلاعات حساب کاربری شما:**\n\n"
            f"🆔 شناسه: `{user_id}`\n"
            f"📊 حجم باقی‌مانده: **{remaining}**",
            reply_markup=keyboard
        )

    elif data == "about_bot":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_home")]])
        await message.edit_text(
            "ℹ️ این ربات مجهز به سیستم سریع پردازش FFmpeg و تغییر کیفیت است.",
            reply_markup=keyboard
        )

    elif data == "back_home":
        user_data[user_id] = {"mode": "main_menu"}
        remaining = "نامحدود (ادمین)" if user_id in ADMINS else f"{user_traffic.get(user_id, 0):.1f} مگابایت"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 شروع پردازش (اول کاور، بعد ویدیو)", callback_data="start_process")],
            [InlineKeyboardButton("👤 حساب کاربری و حجم من", callback_data="user_account")],
            [InlineKeyboardButton("🛒 خرید اشتراک", url="https://t.me/izeucs")],
            [InlineKeyboardButton("ℹ️ درباره ما", callback_data="about_bot")]
        ])
        if user_id in ADMINS:
            keyboard.inline_keyboard.append([InlineKeyboardButton("⚙️ پنل مدیریت ادمین", callback_data="admin_panel")])
        await message.edit_text(f"به منوی اصلی برگشتیم.\n\n🎁 حجم باقی‌مانده: **{remaining}**", reply_markup=keyboard)

    # پنل ادمین
    elif data == "admin_panel" and user_id in ADMINS:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔒 تنظیم قفل کانال", callback_data="admin_set_channel")],
            [InlineKeyboardButton("⭐ اعطای حجم/اشتراک", callback_data="admin_set_sub")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_home")]
        ])
        await message.edit_text("⚙️ **پنل مدیریت ادمین**", reply_markup=keyboard)

    elif data == "admin_stats" and user_id in ADMINS:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]])
        await message.edit_text(f"📊 تعداد کل کاربران ربات: {len(users_db)} نفر", reply_markup=keyboard)

    elif data == "admin_broadcast" and user_id in ADMINS:
        user_data[user_id]["mode"] = "waiting_for_broadcast"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]])
        await message.edit_text("📢 پیام همگانی را بفرستید:", reply_markup=keyboard)

    elif data == "admin_set_channel" and user_id in ADMINS:
        user_data[user_id]["mode"] = "waiting_for_channel"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]])
        await message.edit_text("🔒 یوزرنیم کانال را بفرستید (مثلا @mychannel):", reply_markup=keyboard)

    elif data == "admin_set_sub" and user_id in ADMINS:
        user_data[user_id]["mode"] = "waiting_for_sub_info"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]])
        await message.edit_text("⭐ اطلاعات را به این شکل بفرستید:\n`USER_ID MB`\nمثال:\n`123456789 1000`", reply_markup=keyboard)

    # انتخاب کیفیت خروجی و پردازش نهایی با یک‌بار آپلود
    elif data.startswith("quality_"):
        if user_id not in user_data or user_data[user_id].get("mode") != "waiting_for_quality":
            await callback_query.answer("⚠️ لطفاً مراحل را از ابتدا طی کنید.", show_alert=True)
            return

        await callback_query.answer()
        status_msg = message
        
        video_path = user_data[user_id].get("video_path")
        photo_path = user_data[user_id].get("photo_path")
        output_path = f"output_{user_id}.mp4"

        scale_filter = ""
        if data == "quality_360": scale_filter = "scale=-2:360"
        elif data == "quality_480": scale_filter = "scale=-2:480"
        elif data == "quality_720": scale_filter = "scale=-2:720"
        elif data == "quality_1080": scale_filter = "scale=-2:1080"
        else: scale_filter = "copy"

        await status_msg.edit_text("⚙️ در حال الصاق کاور و پردازش سریع با FFmpeg...")

        if scale_filter == "copy":
            cmd = f"ffmpeg -i '{video_path}' -i '{photo_path}' -map 0 -map 1 -c copy -disposition:v:1 attached_pic '{output_path}' -y"
        else:
            cmd = f"ffmpeg -i '{video_path}' -i '{photo_path}' -filter:v:0 '{scale_filter}' -preset ultrafast -map 0:v -map 0:a? -map 1:v -c:v:0 libx264 -c:a copy -c:v:1 copy -disposition:v:1 attached_pic '{output_path}' -y"

        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()

        await status_msg.edit_text("📤 در حال آپلود ویدیوی نهایی...")
        prog_func = create_progress_callback(status_msg, "📤 **در حال آپلود ویدیوی نهایی:**")

        # ارسال ویدیو بدون نیاز به آپلود مجدد دستی، مستقیم از فایل نهایی روی هاست
        await client.send_video(
            chat_id=user_id,
            video=output_path,
            thumb=photo_path,
            caption="✅ ویدیو با موفقیت پردازش شد و کاور و کیفیت جدید روی آن اعمال گردید.",
            progress=prog_func
        )

        await status_msg.delete()

        # پاکسازی فایل‌ها از روی هاست
        for p in [video_path, photo_path, output_path]:
            if p and os.path.exists(p):
                os.remove(p)

        user_data[user_id] = {"mode": "main_menu"}

# مدیریت پیام‌ها، کاور و ویدیوها بر اساس ترتیب جدید (اول کاور، بعد ویدیو)
@app.on_message(filters.text | filters.video | filters.document | filters.photo)
async def media_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"mode": "main_menu"}
    
    state = user_data[user_id].get("mode")

    # پنل ادمین
    if user_id in ADMINS:
        if state == "waiting_for_broadcast":
            count = 0
            for uid in users_db:
                try:
                    await message.copy(chat_id=uid)
                    count += 1
                except Exception:
                    pass
            user_data[user_id]["mode"] = "main_menu"
            await message.reply_text(f"✅ پیام همگانی به {count} کاربر ارسال شد.")
            return

        elif state == "waiting_for_channel":
            channel_username = message.text.strip()
            settings["forced_channel"] = channel_username
            user_data[user_id]["mode"] = "main_menu"
            await message.reply_text(f"✅ قفل کانال روی {channel_username} تنظیم شد.")
            return

        elif state == "waiting_for_sub_info":
            try:
                parts = message.text.strip().split()
                target_user = int(parts[0])
                added_mb = float(parts[1])
                user_traffic[target_user] = user_traffic.get(target_user, 0) + added_mb
                user_data[user_id]["mode"] = "main_menu"
                await message.reply_text(f"✅ مبلغ {added_mb} MB به کاربر {target_user} اضافه شد.")
                await client.send_message(target_user, f"⭐ حساب شما شارژ شد!\n📊 حجم اضافه شده: {added_mb} مگابایت")
            except Exception:
                await message.reply_text("❌ فرمت اشتباه است. مثال: `123456789 1000`")
            return

    # بررسی حجم کاربر عادی
    if user_id not in ADMINS and user_traffic.get(user_id, 0) <= 0:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 خرید اشتراک از @izeucs", url="https://t.me/izeucs")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_home")]
        ])
        await message.reply_text("❌ حجم تست رایگان شما تمام شده است! برای خرید به @izeucs پیام دهید:", reply_markup=keyboard)
        return

    # مرحله اول: دریافت عکس کاور
    if state == "waiting_for_photo" and message.photo:
        status_msg = await message.reply_text("📥 در حال دریافت عکس کاور...")
        photo_path = await client.download_media(message)
        
        user_data[user_id]["photo_path"] = photo_path
        user_data[user_id]["mode"] = "waiting_for_video"
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="back_home")]])
        await status_msg.edit_text("✅ کاور دریافت شد!\n\n🎬 **مرحله دوم:** حالا لطفاً **ویدیو**ی خود را ارسال کنید:", reply_markup=keyboard)
        return

    # مرحله دوم: دریافت ویدیو و کسر حجم
    elif state == "waiting_for_video" and (message.video or message.document):
        if not await check_forced_sub(client, message):
            return
            
        media_size_mb = (message.video.file_size if message.video else message.document.file_size) / (1024 * 1024)
        
        if user_id not in ADMINS:
            if user_traffic.get(user_id, 0) < media_size_mb:
                await message.reply_text(f"❌ حجم این ویدیو ({media_size_mb:.1f} مگابایت) بیشتر از اعتبار شماست!\n\nخرید اشتراک: @izeucs")
                return
            user_traffic[user_id] -= media_size_mb

        status_msg = await message.reply_text("📥 در حال دانلود ویدیو...")
        prog_func = create_progress_callback(status_msg, "📥 **در حال دانلود ویدیو:**")
        
        video_path = await client.download_media(message, progress=prog_func)
        
        user_data[user_id]["video_path"] = video_path
        user_data[user_id]["mode"] = "waiting_for_quality"
        
        # نمایش منوی شیشه‌ای انتخاب کیفیت
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("360p", callback_data="quality_360"), InlineKeyboardButton("480p", callback_data="quality_480")],
            [InlineKeyboardButton("720p", callback_data="quality_720"), InlineKeyboardButton("1080p", callback_data="quality_1080")],
            [InlineKeyboardButton("⚙️ کیفیت اصلی", callback_data="quality_original")],
            [InlineKeyboardButton("❌ لغو", callback_data="back_home")]
        ])
        
        await status_msg.edit_text("✅ ویدیو دانلود شد!\n\n🎚️ **مرحله سوم:** کیفیت خروجی ویدیو را انتخاب کنید:", reply_markup=keyboard)
        return

    elif state == "main_menu":
        await message.reply_text("⚠️ لطفاً از دکمه‌های شیشه‌ای برای شروع کار استفاده کنید.")

print("Bot is running with Cover-first logic and optimized workflow...")
app.run()
