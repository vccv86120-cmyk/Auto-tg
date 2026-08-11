import os
import re
import asyncio
import random
from datetime import datetime
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
BOT_TOKEN = "8950811882:AAH16uTXcmaj05FdlZq7hfWGZPw-XResp_Y"

# 🔴 آيديات المشرفين المعتمدة
ADMIN_IDS = [1330730590, 7994623189] 

bot_data = {
    "groups": [],
    "messages": [],
    "interval": 60,         # الوقت بالدقائق بين الدورات
    "min_msg_count": 30,    # الحد الأدنى لعدد الرسائل
    "max_msg_count": 35,    # الحد الأقصى لعدد الرسائل
    "mode": "messages",     # 'messages' لنمط عدد الرسائل أو 'time' لنمط الوقت
    "is_running": False,
    # إعدادات وضع الهدوء (أوقات النوم المخصصة)
    "quiet_mode_enabled": True,
    "quiet_start": 2,       # الساعة 2 فجراً
    "quiet_end": 8,         # الساعة 8 صباحاً
    # إحصائيات يومية
    "stats_posts_today": 0,
    "stats_replies_today": 0,
    "stats_last_reset": str(datetime.now().date()),
    "group_posts_count": {}
}

group_counters = {}

def is_quiet_time():
    if not bot_data["quiet_mode_enabled"]:
        return False
    current_hour = datetime.now().hour
    start = bot_data["quiet_start"]
    end = bot_data["quiet_end"]
    if start < end:
        return start <= current_hour < end
    else:
        return current_hour >= start or current_hour < end

def get_next_target(min_c, max_c):
    return random.randint(min_c, max_c)

def get_main_keyboard():
    status = "شغال 🟢" if bot_data["is_running"] else "متوقف 🔴"
    mode_str = "عدد الرسائل 💬" if bot_data["mode"] == "messages" else "التوقيت الزمني ⏱️"
    quiet_status = "مفعل 🌙" if bot_data["quiet_mode_enabled"] else "معطل ☀️"
    
    keyboard = [
        [InlineKeyboardButton(f"حالة البوت: {status}", callback_data="toggle_status")],
        [InlineKeyboardButton(f"🔄 نمط النشر الحالي: [{mode_str}]", callback_data="toggle_mode")],
        [InlineKeyboardButton("🚀 إرسال فوري الآن لكل القروبات", callback_data="force_send_now")],
        [InlineKeyboardButton(f"وضع الهدوء (من {bot_data['quiet_start']} إلى {bot_data['quiet_end']}): [{quiet_status}]", callback_data="toggle_quiet")],
        [InlineKeyboardButton("⚙️ ضبط ساعات الهدوء", callback_data="set_quiet_hours")],
        [InlineKeyboardButton("📊 التقرير اليومي", callback_data="show_daily_report")],
        [InlineKeyboardButton("➕ إضافة قروب", callback_data="add_group"), InlineKeyboardButton("❌ حذف قروب محدد", callback_data="del_group_menu")],
        [InlineKeyboardButton("➕ إضافة رسالة/صورة", callback_data="add_msg"), InlineKeyboardButton("❌ حذف رسالة محددة", callback_data="del_msg_menu")],
        [InlineKeyboardButton("🗑️ حذف كل الرسائل", callback_data="del_all_msg")],
        [InlineKeyboardButton("⚙️ إعدادات الوقت/الرسائل", callback_data="config_settings")],
        [InlineKeyboardButton("📋 عرض الإعدادات العامة", callback_data="show_info")]
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

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    info = f"📊 <b>التقرير والإحصاءات اليومية:</b>\n\n"
    info += f"• <b>المنشورات المرسلة اليوم:</b> {bot_data['stats_posts_today']}\n"
    info += f"• <b>الردود المستلمة اليوم:</b> {bot_data['stats_replies_today']}\n"
    info += f"• <b>حالة الهدوء (النوم):</b> {'نوم (متوقف مؤقتاً) 🌙' if is_quiet_time() else 'نشط 🟢'}\n"
    info += f"• <b>ساعات الهدوء المحددة:</b> من الساعة {bot_data['quiet_start']} إلى الساعة {bot_data['quiet_end']}\n\n"
    info += f"<b>📍 توزيع المنشورات على القروبات:</b>\n"
    
    if bot_data['group_posts_count']:
        for g_id, count in bot_data['group_posts_count'].items():
            info += f"- قروب <code>{g_id}</code>: {count} منشور\n"
    else:
        info += "لا توجد منشورات مسجلة حتى الآن اليوم."
        
    await update.message.reply_text(info, parse_mode="HTML")

async def send_msg_to_group(app, group_id, msg):
    try:
        if msg["type"] == "text":
            await app.bot.send_message(chat_id=group_id, text=msg["text"])
        elif msg["type"] == "photo":
            await app.bot.send_photo(chat_id=group_id, photo=msg["file_id"], caption=msg.get("caption", ""))
        
        bot_data["stats_posts_today"] += 1
        bot_data["group_posts_count"][group_id] = bot_data["group_posts_count"].get(group_id, 0) + 1
        print(f"✅ تم الإرسال بنجاح للقروب {group_id}")
    except Exception as e:
        print(f"❌ خطأ الإرسال للقروب {group_id}: {e}")

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

    elif data == "force_send_now":
        if not bot_data["groups"]:
            await query.message.reply_text("⚠️ لا توجد أي قروبات مضافة حالياً للإرسال إليها.")
            return
        if not bot_data["messages"]:
            await query.message.reply_text("⚠️ لا توجد أي رسائل أو صور مخزنة للإرسال!")
            return
        
        await query.message.reply_text("🚀 جاري إرسال منشور فوري لجميع القروبات المضافة...")
        for g_id in bot_data["groups"]:
            msg = random.choice(bot_data["messages"])
            await send_msg_to_group(context.application, g_id, msg)
        await query.message.reply_text("✅ تم الانتهاء من الإرسال الفوري بنجاح!")

    elif data == "toggle_quiet":
        bot_data["quiet_mode_enabled"] = not bot_data["quiet_mode_enabled"]
        await query.edit_message_reply_markup(reply_markup=get_main_keyboard())

    elif data == "set_quiet_hours":
        context.user_data["action"] = "set_quiet_hours"
        await query.message.reply_text("أدخل ساعات الهدوء بصيغة (بداية-نهاية) بنظام 24 ساعة\nمثال: `2-8` (يعني يبدأ من 2 فجراً إلى 8 صباحاً):")

    elif data == "show_daily_report":
        info = f"📊 <b>التقرير اليومي الشامل:</b>\n\n"
        info += f"• <b>تاريخ اليوم:</b> {bot_data['stats_last_reset']}\n"
        info += f"• <b>إجمالي المنشورات المرسلة:</b> {bot_data['stats_posts_today']}\n"
        info += f"• <b>إجمالي الردود المستلمة:</b> {bot_data['stats_replies_today']}\n"
        info += f"• <b>ساعات الهدوء المفعلة:</b> من {bot_data['quiet_start']} إلى {bot_data['quiet_end']}\n\n"
        info += f"<b>📍 تفاصيل القروبات:</b>\n"
        if bot_data['group_posts_count']:
            for g_id, count in bot_data['group_posts_count'].items():
                info += f"- قروب <code>{g_id}</code>: {count} منشور\n"
        else:
            info += "لا توجد منشورات حتى الآن."
        await query.message.reply_text(info, parse_mode="HTML")

    elif data == "show_info":
        info = f"<b>⚙️ الإعدادات العامة للبوت:</b>\n\n"
        info += f"• <b>نمط النشر المفعل:</b> {'عدد الرسائل 💬' if bot_data['mode'] == 'messages' else 'التوقيت الزمني ⏱️'}\n"
        if bot_data['mode'] == 'messages':
            info += f"• <b>شروط النشر:</b> كل (<b>{bot_data['min_msg_count']}</b> إلى <b>{bot_data['max_msg_count']}</b>) رسالة\n"
        else:
            info += f"• <b>الوقت بين الدورات:</b> {bot_data['interval']} دقيقة\n"
        info += f"• <b>وضع الهدوء:</b> {'مفعل من ' + str(bot_data['quiet_start']) + ' إلى ' + str(bot_data['quiet_end']) + ' 🌙' if bot_data['quiet_mode_enabled'] else 'معطل ☀️'}\n"
        info += f"• <b>عدد القروبات المضافة:</b> {len(bot_data['groups'])}\n"
        info += f"• <b>عدد الرسائل المخزنة:</b> {len(bot_data['messages'])}\n"
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

    elif data == "del_group_menu":
        if not bot_data["groups"]:
            await query.message.reply_text("⚠️ لا توجد أي قروبات مضافة حالياً للحذف.")
            return
        keyboard = []
        for g_id in bot_data["groups"]:
            keyboard.append([InlineKeyboardButton(f"حذف القروب: {g_id}", callback_data=f"del_g_{g_id}")])
        await query.message.reply_text("اختر القروب الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_g_"):
        g_id_to_del = int(data.replace("del_g_", ""))
        if g_id_to_del in bot_data["groups"]:
            bot_data["groups"].remove(g_id_to_del)
            if g_id_to_del in group_counters:
                del group_counters[g_id_to_del]
            await query.message.reply_text(f"✅ تم حذف القروب `{g_id_to_del}` بنجاح!")
        else:
            await query.message.reply_text("❌ القروب غير موجود بالقائمة.")

    elif data == "add_msg":
        context.user_data["action"] = "add_msg"
        await query.message.reply_text("أرسل الآن الرسالة (نص أو صورة) ليتم إضافتها لنظام النشر:")

    elif data == "del_msg_menu":
        if not bot_data["messages"]:
            await query.message.reply_text("⚠️ لا توجد أي رسائل مخزنة حالياً للحذف.")
            return
        keyboard = []
        for index, msg in enumerate(bot_data["messages"]):
            snippet = msg.get("text", msg.get("caption", "صورة بدون نص"))[:25]
            keyboard.append([InlineKeyboardButton(f"[{index+1}] {snippet}...", callback_data=f"del_m_{index}")])
        await query.message.reply_text("اختر الرسالة التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_m_"):
        idx = int(data.replace("del_m_", ""))
        if 0 <= idx < len(bot_data["messages"]):
            bot_data["messages"].pop(idx)
            await query.message.reply_text(f"🗑️ تم حذف الرسالة رقم ({idx+1}) بنجاح!")
        else:
            await query.message.reply_text("❌ رقم الرسالة غير صحيح.")

    elif data == "del_all_msg":
        bot_data["messages"].clear()
        await query.message.reply_text("🗑️ تم مسح جميع الرسائل والصور بنجاح.")

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0

    if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
        bot_data["stats_replies_today"] += 1
        
        sender_name = update.effective_user.full_name
        username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون معرف"
        chat_title = update.effective_chat.title or "قروب"
        
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
                await context.bot.send_message(chat_id=admin_id, text=notification, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e:
                print(f"خطأ في إرسال إشعار الرد للمشرف {admin_id}: {e}")

    if chat_id in bot_data["groups"] and user_id != context.bot.id:
        if bot_data["is_running"] and bot_data["mode"] == "messages" and not is_quiet_time():
            if chat_id not in group_counters:
                group_counters[chat_id] = {
                    "current": 0,
                    "target": get_next_target(bot_data["min_msg_count"], bot_data["max_msg_count"])
                }
            
            group_counters[chat_id]["current"] += 1
            if group_counters[chat_id]["current"] >= group_counters[chat_id]["target"]:
                if bot_data["messages"]:
                    msg = random.choice(bot_data["messages"])
                    await send_msg_to_group(context.application, chat_id, msg)
                group_counters[chat_id]["current"] = 0
                group_counters[chat_id]["target"] = get_next_target(bot_data["min_msg_count"], bot_data["max_msg_count"])
        return

    if update.effective_chat.type == "private" and user_id not in ADMIN_IDS:
        sender_name = update.effective_user.full_name
        username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون معرف"
        
        notification = f"📩 <b>وصلتك رسالة جديدة في الخاص!</b>\n\n• <b>المرسل:</b> {sender_name}\n• <b>المعرف:</b> {username}\n• <b>الآيدي:</b> <code>{user_id}</code>\n\n<i>للرد على الشخص، قم بعمل (Reply) على هذه الرسالة!</i>"
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=notification, parse_mode="HTML")
                await context.bot.forward_message(chat_id=admin_id, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except Exception as e:
                print(f"خطأ في توجيه الرسالة للمشرف {admin_id}: {e}")
        return

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
                await context.bot.copy_message(chat_id=target_user_id, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
                await update.message.reply_text("✅ تم إرسال الرد للشخص بنجاح!")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ تعذر إرسال الرد: {e}")
                return

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

    elif action == "set_quiet_hours":
        try:
            parts = update.message.text.strip().split("-")
            start_h, end_h = int(parts[0]), int(parts[1])
            if 0 <= start_h <= 23 and 0 <= end_h <= 23:
                bot_data["quiet_start"] = start_h
                bot_data["quiet_end"] = end_h
                await update.message.reply_text(f"🌙 تم تحديث ساعات الهدوء بنجاح لتصبح: من الساعة {start_h} إلى الساعة {end_h}")
            else:
                await update.message.reply_text("❌ يرجى إدخال ساعات صحيحة بين 0 و 23.")
        except Exception:
            await update.message.reply_text("❌ الصيغة غير صحيحة. استخدم الصيغة التالية: `2-8`")

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
                await update.message.reply_text(f"🎯 تم ضبط نطاق الرسائل: كل **{min_c}** إلى **{max_c}** رسالة.")
            else:
                await update.message.reply_text("❌ تأكد من الأرقام بشكل صحيح (مثال: `30-35`).")
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

async def daily_auto_report_loop(app):
    while True:
        await asyncio.sleep(300)
        current_date_str = str(datetime.now().date())
        if bot_data["stats_last_reset"] != current_date_str:
            old_date = bot_data["stats_last_reset"]
            posts = bot_data["stats_posts_today"]
            replies = bot_data["stats_replies_today"]
            
            report = (
                f"📈 <b>التقرير اليومي التلقائي للبوت ({old_date})</b>\n\n"
                f"• إجمالي المنشورات المرسلة: <b>{posts}</b>\n"
                f"• إجمالي الردود المستلمة: <b>{replies}</b>\n"
                f"• حالة النظام: تم بدء يوم جديد وتصفير العدادات بنجاح 🟢"
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await app.bot.send_message(chat_id=admin_id, text=report, parse_mode="HTML")
                except Exception as e:
                    print(f"خطأ في إرسال التقرير التلقائي للمشرف {admin_id}: {e}")
            
            bot_data["stats_posts_today"] = 0
            bot_data["stats_replies_today"] = 0
            bot_data["group_posts_count"] = {}
            bot_data["stats_last_reset"] = current_date_str

async def time_based_post_loop(app):
    first_start = True
    while True:
        if bot_data["is_running"] and bot_data["mode"] == "time" and bot_data["groups"] and bot_data["messages"] and not is_quiet_time():
            if first_start:
                await asyncio.sleep(random.randint(60, 180))
                first_start = False

            job_queue = []
            for g_id in bot_data["groups"]:
                group_msgs = list(bot_data["messages"])
                random.shuffle(group_msgs)
                for msg in group_msgs:
                    job_queue.append((g_id, msg))
            
            random.shuffle(job_queue)

            for g_id, msg in job_queue:
                if not bot_data["is_running"] or bot_data["mode"] != "time" or is_quiet_time():
                    break
                
                await send_msg_to_group(app, g_id, msg)
                await asyncio.sleep(random.randint(30, 90))

            if bot_data["is_running"] and bot_data["mode"] == "time":
                base_sec = bot_data["interval"] * 60
                await asyncio.sleep(random.randint(int(base_sec * 0.9), int(base_sec * 1.1)))
        else:
            first_start>True if False else None
            await asyncio.sleep(10)

async def post_init(app):
    asyncio.create_task(time_based_post_loop(app))
    asyncio.create_task(daily_auto_report_loop(app))

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_messages))

    print("البوت يعمل بالتوكن الجديد وجاهز...")
    app.run_polling(drop_pending_updates=True)
