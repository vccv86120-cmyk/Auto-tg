import os
import re
import asyncio
import random
import nest_asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# حل مشكلة Event Loop في إصدارات بايثون
nest_asyncio.apply()

# ==================== خادم التفعيل المجاني لـ Render ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

    def log_message(self, format, *args):
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

Thread(target=run_health_check_server, daemon=True).start()

# ==================== الإعدادات ====================
BOT_TOKEN = "8950811882:AAEssHhN928jnIitxp3EMZEc_-at7JBXqTc"

# 🔴 آيديات المشرفين المعتمدة
ADMIN_IDS = [1330730590, 7994623189] 

bot_data = {
    "groups": [],
    "messages": [],
    "interval": 60,         # الوقت بالدقائق (في حال اختيار نمط الوقت)
    "min_msg_count": 30,    # الحد الأدنى لعدد الرسائل
    "max_msg_count": 35,    # الحد الأقصى لعدد الرسائل
    "mode": "messages",     # 'messages' لنمط عدد الرسائل أو 'time' لنمط الوقت
    "is_running": False
}

# عداد الرسائل لكل قروب
group_counters = {}

def get_next_target(min_c, max_c):
    return random.randint(min_c, max_c)

def get_main_keyboard():
    status = "شغال 🟢" if bot_data["is_running"] else "متوقف 🔴"
    mode_str = "عدد الرسائل 💬" if bot_data["mode"] == "messages" else "التوقيت الزمني ⏱️"
    
    keyboard = [
        [InlineKeyboardButton(f"حالة البوت: {status}", callback_data="toggle_status")],
        [InlineKeyboardButton(f"🔄 نمط النشر الحالي: [{mode_str}]", callback_data="toggle_mode")],
        [InlineKeyboardButton("➕ إضافة قروب", callback_data="add_group"), InlineKeyboardButton("❌ حذف قروب", callback_data="del_group")],
        [InlineKeyboardButton("➕ إضافة رسالة/صورة", callback_data="add_msg"), InlineKeyboardButton("❌ حذف كل الرسائل", callback_data="del_msg")],
        [InlineKeyboardButton("⚙️ إعدادات وقت/عدد الرسائل", callback_data="config_settings")],
        [InlineKeyboardButton("📋 عرض الإعدادات الحالية", callback_data="show_info")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text(
            "أهلاً بك في لوحة تحكم بوت النشر التلقائي الذكي!\nاختر ما تريد القيام به من الأزرار أدناه:",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text("أهلاً بك! تم استلام رسالتك وسنرد عليك في أقرب وقت.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        return

    data = query.data

    if data == "toggle_status":
        bot_data["is_running"] = not bot_data["is_running"]
        await query.edit_message_reply_markup(reply_markup=get_main_keyboard())

    elif data == "toggle_mode":
        bot_data["mode"] = "time" if bot_data["mode"] == "messages" else "messages"
        await query.edit_message_reply_markup(reply_markup=get_main_keyboard())

    elif data == "show_info":
        info = f"<b>📊 الإعدادات الحالية:</b>\n\n"
        info += f"• <b>نمط النشر المفعل:</b> {'عدد الرسائل 💬' if bot_data['mode'] == 'messages' else 'التوقيت الزمني ⏱️'}\n"
        if bot_data['mode'] == 'messages':
            info += f"• <b>شروط النشر:</b> كل (<b>{bot_data['min_msg_count']}</b> إلى <b>{bot_data['max_msg_count']}</b>) رسالة بالقروب\n"
        else:
            info += f"• <b>الوقت بين الدورات:</b> {bot_data['interval']} دقيقة\n"
        
        info += f"• <b>عدد القروبات:</b> {len(bot_data['groups'])}\n"
        info += f"• <b>عدد الرسائل/الصور المخزنة:</b> {len(bot_data['messages'])}\n"
        info += f"• <b>حالة البوت:</b> {'مفعل 🟢' if bot_data['is_running'] else 'متوقف 🔴'}"
        await query.message.reply_text(info, parse_mode="HTML")

    elif data == "config_settings":
        if bot_data["mode"] == "messages":
            context.user_data["action"] = "set_msg_range"
            await query.message.reply_text("أدخل نطاق عدد الرسائل كالتالي (الأدنى-الأقصى)\nمثال: `30-35` :")
        else:
            context.user_data["action"] = "set_interval"
            await query.message.reply_text("أدخل الوقت الأساسي بالدقائق (مثال: `60` للساعة):")

    elif data == "add_group":
        context.user_data["action"] = "add_group"
        await query.message.reply_text("أرسل الآن رقم Chat ID الخاص بالقروب (مثال: `-100123456789`):")

    elif data == "del_group":
        context.user_data["action"] = "del_group"
        await query.message.reply_text("أرسل رقم القروب الذي تريد حذفه من القائمة:")

    elif data == "add_msg":
        context.user_data["action"] = "add_msg"
        await query.message.reply_text("أرسل الآن الرسالة (نص أو صورة) ليتم إضافتها لنظام النشر:")

    elif data == "del_msg":
        bot_data["messages"].clear()
        await query.message.reply_text("🗑️ تم مسح جميع الرسائل والصور بنجاح.")

async def send_random_msg_to_group(app, group_id):
    """ إرسال رسالة عشوائية لقروب محدد """
    if not bot_data["messages"]:
        return
    
    msg = random.choice(bot_data["messages"])
    try:
        if msg["type"] == "text":
            await app.bot.send_message(chat_id=group_id, text=msg["text"])
        elif msg["type"] == "photo":
            await app.bot.send_photo(chat_id=group_id, photo=msg["file_id"], caption=msg.get("caption", ""))
        print(f"✅ [نمط الرسائل] تم الإرسال للقروب {group_id}")
    except Exception as e:
        print(f"❌ خطأ الإرسال للقروب {group_id}: {e}")

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0

    # 🔔 1️⃣ كشف ردود الأعضاء على رسائل/إعلانات البوت داخل القروبات
    if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
        sender_name = update.effective_user.full_name
        username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون معرف"
        chat_title = update.effective_chat.title or "قروب"
        
        # استخراج رابط الرسالة المباشر
        msg_link = update.message.link
        if not msg_link and str(chat_id).startswith("-100"):
            clean_id = str(chat_id).replace("-100", "")
            msg_link = f"https://t.me/c/{clean_id}/{update.message.message_id}"
        elif not msg_link:
            msg_link = "#"

        reply_text = update.message.text or update.message.caption or "[محتوى وسائط]"
        
        notification = (
            f"💬 <b>وصلك رد جديد على إعلانك!</b>\n\n"
            f"• <b>القروب:</b> {chat_title}\n"
            f"• <b>المرسل:</b> {sender_name} ({username})\n"
            f"• <b>الرسالة:</b> <i>{reply_text}</i>\n\n"
            f"🔗 <a href='{msg_link}'>اضغط هنا للذهاب للرسالة بالقروب</a>"
        )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=notification,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except Exception as e:
                print(f"خطأ في إرسال إشعار الرد للمشرف {admin_id}: {e}")

    # 2️⃣ متابعة وعدّ الرسائل في القروبات المضافة (نمط عدد الرسائل)
    if chat_id in bot_data["groups"] and user_id != context.bot.id:
        if bot_data["is_running"] and bot_data["mode"] == "messages":
            if chat_id not in group_counters:
                group_counters[chat_id] = {
                    "current": 0,
                    "target": get_next_target(bot_data["min_msg_count"], bot_data["max_msg_count"])
                }
            
            group_counters[chat_id]["current"] += 1
            print(f"قروب {chat_id}: الرسائل {group_counters[chat_id]['current']}/{group_counters[chat_id]['target']}")

            if group_counters[chat_id]["current"] >= group_counters[chat_id]["target"]:
                await send_random_msg_to_group(context.application, chat_id)
                group_counters[chat_id]["current"] = 0
                group_counters[chat_id]["target"] = get_next_target(bot_data["min_msg_count"], bot_data["max_msg_count"])
        return

    # 📩 3️⃣ استقبال رسائل الخاص من الأعضاء للردود المباشرة
    if update.effective_chat.type == "private" and user_id not in ADMIN_IDS:
        sender_name = update.effective_user.full_name
        username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون معرف"
        
        notification = f"📩 <b>وصلتك رسالة جديدة في الخاص!</b>\n\n• <b>المرسل:</b> {sender_name}\n• <b>المعرف:</b> {username}\n• <b>الآيدي:</b> <code>{user_id}</code>\n\n<i>للرد على الشخص، قم بعمل (Reply) على هذه الرسالة!</i>"
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=notification, parse_mode="HTML")
                await context.bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
            except Exception as e:
                print(f"خطأ في توجيه الرسالة للمشرف {admin_id}: {e}")
        return

    # 💬 4️⃣ ردود المشرفين على رسائل الخاص
    if user_id in ADMIN_IDS and update.message.reply_to_message:
        replied_msg = update.message.reply_to_message
        target_user_id = None

        if replied_msg.forward_from:
            target_user_id = replied_msg.forward_from.id
        elif replied_msg.text or replied_msg.caption:
            text = replied_msg.text or replied_msg.caption
            match = re.search(r"الآيدي:\s*(\d+)", text)
            if match:
                target_user_id = int(match.group(1))

        if target_user_id:
            try:
                await context.bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                await update.message.reply_text("✅ تم إرسال الرد للشخص بنجاح!")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ تعذر إرسال الرد: {e}")
                return

    # ⚙️ 5️⃣ أوامر لوحة تحكم المشرفين
    action = context.user_data.get("action")

    if action == "add_group":
        try:
            g_id = int(update.message.text.strip())
            if g_id not in bot_data["groups"]:
                bot_data["groups"].append(g_id)
                group_counters[g_id] = {
                    "current": 0,
                    "target": get_next_target(bot_data["min_msg_count"], bot_data["max_msg_count"])
                }
                await update.message.reply_text(f"✅ تم إضافة القروب `{g_id}` بنجاح!")
            else:
                await update.message.reply_text("⚠️ القروب مضاف سابقاً.")
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح للقروب.")

    elif action == "del_group":
        try:
            g_id = int(update.message.text.strip())
            if g_id in bot_data["groups"]:
                bot_data["groups"].remove(g_id)
                if g_id in group_counters:
                    del group_counters[g_id]
                await update.message.reply_text("✅ تم حذف القروب بنجاح.")
            else:
                await update.message.reply_text("❌ الرقم غير موجود بالقائمة.")
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")

    elif action == "add_msg":
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            caption = update.message.caption or ""
            bot_data["messages"].append({"type": "photo", "file_id": photo_id, "caption": caption})
            await update.message.reply_text("✅ تم حفظ الصورة والنص بنجاح!")
        elif update.message.text:
            bot_data["messages"].append({"type": "text", "text": update.message.text})
            await update.message.reply_text("✅ تم حفظ النص بنجاح!")

    elif action == "set_msg_range":
        try:
            parts = update.message.text.strip().split("-")
            min_c, max_c = int(parts[0]), int(parts[1])
            if 0 < min_c <= max_c:
                bot_data["min_msg_count"] = min_c
                bot_data["max_msg_count"] = max_c
                await update.message.reply_text(f"🎯 تم ضبط النطاق الإعلاني: كل **{min_c}** إلى **{max_c}** رسالة بالقروب.")
            else:
                await update.message.reply_text("❌ التأكد من الأرقام بشكل صحيح (مثال: `30-35`).")
        except Exception:
            await update.message.reply_text("❌ طريقة الإدخال خاطئة. استخدم الصيغة: `30-35`")

    elif action == "set_interval":
        try:
            minutes = int(update.message.text.strip())
            if minutes > 0:
                bot_data["interval"] = minutes
                await update.message.reply_text(f"⏱️ تم ضبط الوقت بين الدورات إلى **{minutes} دقيقة**.")
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح بالدقائق.")

    context.user_data["action"] = None

async def time_based_post_loop(app):
    """ النشر عبر نمط الوقت الزمني """
    first_start = True
    while True:
        if bot_data["is_running"] and bot_data["mode"] == "time" and bot_data["groups"] and bot_data["messages"]:
            if first_start:
                await asyncio.sleep(random.randint(60, 180))
                first_start = False

            job_queue = []
            for g_id in bot_data["groups"]:
                for msg in bot_data["messages"]:
                    job_queue.append((g_id, msg))
            
            random.shuffle(job_queue)

            for g_id, msg in job_queue:
                if not bot_data["is_running"] or bot_data["mode"] != "time":
                    break
                try:
                    if msg["type"] == "text":
                        await app.bot.send_message(chat_id=g_id, text=msg["text"])
                    elif msg["type"] == "photo":
                        await app.bot.send_photo(chat_id=g_id, photo=msg["file_id"], caption=msg.get("caption", ""))
                    print(f"✅ [نمط الوقت] تم الإرسال للقروب {g_id}")
                except Exception as e:
                    print(f"❌ خطأ: {e}")
                
                await asyncio.sleep(random.randint(30, 90))

            if bot_data["is_running"] and bot_data["mode"] == "time":
                base_sec = bot_data["interval"] * 60
                await asyncio.sleep(random.randint(int(base_sec * 0.9), int(base_sec * 1.1)))
        else:
            first_start = True
            await asyncio.sleep(5)

async def post_init(app):
    asyncio.create_task(time_based_post_loop(app))

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_messages))

    print("البوت يعمل بنجاح مع نظام إشعارات الردود المباشرة...")
    app.run_polling(drop_pending_updates=True)
