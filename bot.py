import os
import json
import asyncio
import time
import threading
import aiohttp
from http.server import HTTPServer, BaseHTTPRequestHandler
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from hydrogram.errors import UserNotParticipant

# --- راه‌اندازی سرور وب کوچک برای زنده نگه داشتن رندر ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ZEUC TV Bot is running perfectly!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()
# ---------------------------------------------------------

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

USERS_FILE = "users_db.json"
TRAFFIC_FILE = "user_traffic.json"
SETTINGS_FILE = "settings.json"

def load_json(filename, default_val):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(default_val, dict):
                    return {int(k) if str(k).lstrip('-').isdigit() else k: v for k, v in data.items()}
                return data
        except Exception:
            return default_val
    return default_val

def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

users_db = load_json(USERS_FILE, {})
user_traffic = load_json(TRAFFIC_FILE, {})
settings = load_json(SETTINGS_FILE, {"forced_channel": None})
user_data = {}

def get_reply_keyboard(user_id):
    keyboard = [
        [KeyboardButton("🎬 شروع پردازش (کاور + ویدیو)"), KeyboardButton("🔗 تبدیل لینک به ویدیو")],
        [KeyboardButton("👤 حساب من"), KeyboardButton("🛒 خرید اشتراک")],
        [KeyboardButton("ℹ️ راهنما")]
    ]
    if user_id in ADMINS:
        keyboard.append([KeyboardButton("⚙️ پنل مدیریت ادمین")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_subtitle_keyboard():
    keyboard = [
        [KeyboardButton("⏭️ مرحله بعد (بدون زیرنویس)")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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

async def download_file_from_url(url, output_path, message):
    start_time = time.time()
    last_update_time = [0]
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=60)
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=True) as response:
            if response.status != 200:
                raise Exception("خطا در دسترسی به لینک (کد وضعیت: {})".format(response.status))
            
            total_size = int(response.headers.get('Content-Length', 0))
            if total_size > 512 * 1024 * 1024:
                raise Exception("LIMIT_EXCEEDED")

            downloaded = 0
            with open(output_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(2048 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            now = time.time()
                            if now - last_update_time[0] >= 1.5:
                                last_update_time[0] = now
                                percentage = downloaded * 100 / total_size
                                elapsed = now - start_time
                                speed = downloaded / elapsed if elapsed > 0 else 0
                                
                                current_mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024)
                                speed_mb = speed / (1024 * 1024)

                                filled = int(percentage // 10)
                                progress_bar = "█" * filled + "░" * (10 - filled)
                                
                                txt = (
                                    f"📥 **در حال دانلود از لینک:**\n\n"
                                    f"[{progress_bar}] {percentage:.1f}%\n\n"
                                    f"📊 حجم: {current_mb:.1f} MB از {total_mb:.1f} MB\n"
                                    f"⚡ سرعت: {speed_mb:.1f} MB/s"
                                )
                                try:
                                    await message.edit_text(txt)
                                except Exception:
                                    pass

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
    try:
        user_id = message.from_user.id
        name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
        username = f"@{message.from_user.username}" if message.from_user.username else "ندارد"
        
        users_db[user_id] = {"name": name if name else "بدون نام", "username": username}
        save_json(USERS_FILE, users_db)
        
        if user_id not in user_traffic and user_id not in ADMINS:
            user_traffic[user_id] = 500.0
            save_json(TRAFFIC_FILE, user_traffic)

        user_data[user_id] = {"mode": "main_menu"}
        
        if not await check_forced_sub(client, message):
            return

        remaining = "نامحدود (ادمین)" if user_id in ADMINS else f"{user_traffic.get(user_id, 0):.1f} مگابایت"

        await message.reply_text(
            f"سلام! 👋 به ربات مدیریت ویدیو خوش آمدید.\n\n"
            f"🎁 حجم هدیه تست شما: **{remaining}**",
            reply_markup=get_reply_keyboard(user_id)
        )
    except Exception as e:
        print(f"Error in start: {e}")

@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    try:
        data = callback_query.data
        user_id = callback_query.from_user.id
        message = callback_query.message

        if data == "check_membership":
            if await check_forced_sub(client, message):
                await message.edit_text("✅ عضویت تایید شد!")
            else:
                await callback_query.answer("⚠️ هنوز عضو نشده‌اید!", show_alert=True)
            return

        if data == "cancel":
            user_data[user_id] = {"mode": "main_menu"}
            await message.edit_text("❌ عملیات لغو شد.", reply_markup=get_reply_keyboard(user_id))
            return
    except Exception as e:
        print(f"Error in callback: {e}")

async def finalize_and_send(client, message, user_id, video_path, photo_path, subtitle_path=None):
    output_path = f"output_{user_id}.mp4"
    status_msg = await message.reply_text("⚙️ در حال پردازش ویدیو و اعمال تنظیمات...")

    try:
        v_str = str(video_path) if video_path else ""
        p_str = str(photo_path) if photo_path else ""
        
        if subtitle_path and os.path.exists(subtitle_path):
            sub_str = str(subtitle_path)
            sub_escaped = sub_str.replace("'", "\\'").replace(":", "\\:")
            cmd = f"ffmpeg -i '{v_str}' -vf \"subtitles='{sub_escaped}'\" -c:v libx264 -preset ultrafast -crf 23 -c:a copy -movflags +faststart '{output_path}' -y"
        else:
            cmd = f"ffmpeg -i '{v_str}' -map 0:v -map 0:a -c copy -movflags +faststart '{output_path}' -y"

        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()

        await status_msg.edit_text("📤 در حال ارسال ویدیوی نهایی...")
        upload_prog = create_progress_callback(status_msg, "📤 **در حال ارسال ویدیوی نهایی:**")

        await client.send_video(
            chat_id=user_id,
            video=output_path,
            thumb=p_str if p_str else None,
            caption="✅ ویدیو با موفقیت آماده و ارسال شد.",
            progress=upload_prog
        )

        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ خطا در پردازش نهایی: `{str(e)}`")
    finally:
        for p in [video_path, photo_path, subtitle_path, output_path]:
            if p and os.path.exists(str(p)):
                try:
                    os.remove(str(p))
                except:
                    pass
        user_data[user_id] = {"mode": "main_menu"}
        await message.reply_text("لطفاً یک گزینه انتخاب کنید:", reply_markup=get_reply_keyboard(user_id))

@app.on_message(filters.text | filters.video | filters.document | filters.photo)
async def media_handler(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        text = message.text
        
        name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
        username = f"@{message.from_user.username}" if message.from_user.username else "ندارد"
        
        if user_id not in users_db:
            users_db[user_id] = {"name": name if name else "بدون نام", "username": username}
            save_json(USERS_FILE, users_db)

        if user_id not in user_data:
            user_data[user_id] = {"mode": "main_menu"}
        
        state = user_data[user_id].get("mode")

        if text == "🎬 شروع پردازش (کاور + ویدیو)":
            if user_id not in ADMINS and user_traffic.get(user_id, 0) <= 0:
                await message.reply_text("❌ حجم تست شما تمام شده است. خرید اشتراک: @izeucs")
                return
            user_data[user_id] = {"mode": "waiting_for_photo"}
            await message.reply_text("🖼️ **مرحله اول:** لطفاً **عکس کاور** مورد نظرتان را ارسال کنید:")
            return

        elif text == "🔗 تبدیل لینک به ویدیو":
            if user_id not in ADMINS and user_traffic.get(user_id, 0) <= 0:
                await message.reply_text("❌ حجم تست شما تمام شده است. خرید اشتراک: @izeucs")
                return
            user_data[user_id] = {"mode": "waiting_for_link_photo"}
            await message.reply_text("🖼️ **مرحله اول (تبدیل لینک):** لطفاً **عکس کاور** مورد نظرتان را ارسال کنید:")
            return

        elif text == "👤 حساب من":
            remaining = "نامحدود (ادمین)" if user_id in ADMINS else f"{user_traffic.get(user_id, 0):.1f} مگابایت"
            await message.reply_text(f"👤 حساب کاربری:\n🆔 شناسه: `{user_id}`\n📊 حجم باقی‌مانده: **{remaining}**")
            return

        elif text == "🛒 خرید اشتراک":
            await message.reply_text("🛒 برای خرید اشتراک و افزایش حجم، به پشتیبانی پیام دهید:\n👉 @izeucs")
            return

        elif text == "ℹ️ راهنما":
            await message.reply_text("ℹ️ این ربات برای قرار دادن کاور، چسباندن زیرنویس و تبدیل لینک مستقیم طراحی شده است.")
            return

        elif text == "⏭️ مرحله بعد (بدون زیرنویس)":
            if state in ["waiting_for_subtitle", "waiting_for_link_subtitle"]:
                v_path = user_data[user_id].get("video_path")
                p_path = user_data[user_id].get("photo_path")
                await finalize_and_send(client, message, user_id, v_path, p_path, None)
                return

        if state == "waiting_for_photo" and message.photo:
            status_msg = await message.reply_text("📥 در حال دریافت عکس کاور...")
            photo_path = str(await client.download_media(message))
            user_data[user_id]["photo_path"] = photo_path
            user_data[user_id]["mode"] = "waiting_for_video"
            await status_msg.edit_text("✅ کاور دریافت شد!\n\n🎬 **مرحله دوم:** حالا فایل **ویدیو** را بفرستید:")
            return

        elif state == "waiting_for_link_photo" and message.photo:
            status_msg = await message.reply_text("📥 در حال دریافت عکس کاور...")
            photo_path = str(await client.download_media(message))
            user_data[user_id]["photo_path"] = photo_path
            user_data[user_id]["mode"] = "waiting_for_link_url"
            await status_msg.edit_text("✅ کاور دریافت شد!\n\n🔗 **مرحله دوم:** حالا **لینک مستقیم دانلود ویدیو** را ارسال کنید:")
            return

        elif state == "waiting_for_link_url" and text and text.startswith("http"):
            if not await check_forced_sub(client, message):
                return

            status_msg = await message.reply_text("🔍 در حال بررسی لینک و استعلام حجم فایل...")
            video_path = f"downloaded_{user_id}.mp4"

            try:
                await download_file_from_url(text, video_path, status_msg)
            except Exception as e:
                if str(e) == "LIMIT_EXCEEDED":
                    await status_msg.edit_text("❌ حجم فایل موجود در لینک بیشتر از حد مجاز (۵۱۲ مگابایت) است.")
                else:
                    await status_msg.edit_text(f"❌ خطا در دانلود فایل از لینک:\n`{str(e)}`")
                if os.path.exists(video_path):
                    os.remove(video_path)
                user_data[user_id] = {"mode": "main_menu"}
                await message.reply_text("لطفاً از منو انتخاب کنید:", reply_markup=get_reply_keyboard(user_id))
                return

            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            if user_id not in ADMINS:
                if user_traffic.get(user_id, 0) < file_size_mb:
                    await status_msg.edit_text(f"❌ حجم فایل ({file_size_mb:.1f} MB) از اعتبار شما بیشتر است!")
                    if os.path.exists(video_path):
                        os.remove(video_path)
                    user_data[user_id] = {"mode": "main_menu"}
                    await message.reply_text("لطفاً از منو انتخاب کنید:", reply_markup=get_reply_keyboard(user_id))
                    return
                user_traffic[user_id] -= file_size_mb
                save_json(TRAFFIC_FILE, user_traffic)

            user_data[user_id]["video_path"] = video_path
            user_data[user_id]["mode"] = "waiting_for_link_subtitle"
            
            await status_msg.edit_text(
                "✅ ویدیو از لینک دانلود شد!\n\n"
                "📝 **مرحله سوم (اختیاری):** لطفاً **فایل زیرنویس** (`.srt`) خود را بفرستید یا روی دکمه زیر کلیک کنید:",
                reply_markup=get_subtitle_keyboard()
            )
            return

        elif state == "waiting_for_video" and (message.video or message.document):
            if not await check_forced_sub(client, message):
                return
                
            media_size_mb = (message.video.file_size if message.video else message.document.file_size) / (1024 * 1024)
            
            if media_size_mb > 512:
                await message.reply_text(f"❌ حجم ویدیو ({media_size_mb:.1f} MB) بیشتر از حد مجاز (۵۱۲ مگابایت) است!")
                return

            if user_id not in ADMINS:
                if user_traffic.get(user_id, 0) < media_size_mb:
                    await message.reply_text(f"❌ حجم ویدیو ({media_size_mb:.1f} MB) از اعتبار شما بیشتر است!")
                    return
                user_traffic[user_id] -= media_size_mb
                save_json(TRAFFIC_FILE, user_traffic)

            status_msg = await message.reply_text("📥 در حال دانلود ویدیو...")
            prog_func = create_progress_callback(status_msg, "📥 **در حال دانلود ویدیو:**")
            
            video_path = str(await client.download_media(message, progress=prog_func))
            user_data[user_id]["video_path"] = video_path
            user_data[user_id]["mode"] = "waiting_for_subtitle"
            
            await status_msg.edit_text(
                "✅ ویدیو دانلود شد!\n\n"
                "📝 **مرحله سوم (اختیاری):** لطفاً **فایل زیرنویس** (`.srt`) خود را بفرستید یا روی دکمه زیر بزنید:",
                reply_markup=get_subtitle_keyboard()
            )
            return

        elif state in ["waiting_for_subtitle", "waiting_for_link_subtitle"] and (message.document or (text and text.endswith(('.srt', '.vtt')))):
            status_msg = await message.reply_text("📥 در حال دریافت فایل زیرنویس...")
            sub_path = str(await client.download_media(message))
            
            v_path = user_data[user_id].get("video_path")
            p_path = user_data[user_id].get("photo_path")
            
            await status_msg.delete()
            await finalize_and_send(client, message, user_id, v_path, p_path, sub_path)
            return

        elif state == "main_menu":
            await message.reply_text("⚠️ لطفاً از دکمه‌های پایین صفحه استفاده کنید:", reply_markup=get_reply_keyboard(user_id))
    except Exception as e:
        print(f"Error in media_handler: {e}")

print("Bot is running with string-converted paths for FFmpeg/Subtitles...")
app.run()
