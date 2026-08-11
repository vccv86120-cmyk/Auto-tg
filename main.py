import os
import asyncio
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

# حل مشكلة Event Loop في إصدارات بايثون الحديثة
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
BOT_TOKEN = "8950811882:AAGhfE8JGyjanJgEGPxJSUJHBDo4SjJDea0"

bot_data = {
    "groups": [],
    "messages": [],
    "interval": 60,
    "is_running": False
}

def get_main_keyboard():
    status = "شغال 🟢" if bot_data["is_running"] else "متوقف 🔴"
    keyboard = [
        [InlineKeyboardButton(f"حالة البوت: {status}", callback_data="toggle_status")],
        [InlineKeyboardButton("➕ إضافة قروب", callback_data="add_group"), InlineKeyboardButton("❌ حذف قروب", callback_data="del_group")],
        [InlineKeyboardButton("➕ إضافة رسالة/صورة", callback_data="add_msg"), InlineKeyboardButton("❌ حذف كل الرسائل", callback_data="del_msg")],
        [InlineKeyboardButton("⏱️ تغيير وقت التكرار", callback_data="set_interval")],
        [InlineKeyboardButton("📋 عرض الإعدادات الحالية", callback_data="show_info")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في لوحة تحكم بوت النشر التلقائي!\nاختر ما تريد القيام به من الأزرار أدناه:",
        reply_markup=get_main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "toggle_status":
        bot_data["is_running"] = not bot_data["is_running"]
        await query.edit_message_reply_markup(reply_markup=get_main_keyboard())

    elif data == "show_info":
        info = f"<b>📊 الإعدادات الحالية:</b>\n\n"
        info += f"• <b>عدد القروبات:</b> {len(bot_data['groups'])}\n"
        info += f"• <b>عدد الرسائل والصور:</b> {len(bot_data['messages'])}\n"
        info += f"• <b>التكرار كل:</b> {bot_data['interval']} دقيقة\n"
        info += f"• <b>حالة النشر:</b> {'مفعل 🟢' if bot_data['is_running'] else 'متوقف 🔴'}"
        await query.message.reply_text(info, parse_mode="HTML")

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

    elif data == "set_interval":
        context.user_data["action"] = "set_interval"
        await query.message.reply_text("أدخل الوقت الفاصل بين الرسائل **بالدقائق** (مثال: `30`):")

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("action")

    if action == "add_group":
        try:
            group_id = int(update.message.text.strip())
            if group_id not in bot_data["groups"]:
                bot_data["groups"].append(group_id)
                await update.message.reply_text(f"✅ تم إضافة القروب `{group_id}` بنجاح!")
            else:
                await update.message.reply_text("⚠️ هذا القروب مضاف سابقاً.")
        except ValueError:
            await update.message.reply_text("❌ خطأ: يرجى إدخال رقم صحيح للقروب.")

    elif action == "del_group":
        try:
            group_id = int(update.message.text.strip())
            if group_id in bot_data["groups"]:
                bot_data["groups"].remove(group_id)
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

    elif action == "set_interval":
        try:
            minutes = int(update.message.text.strip())
            if minutes > 0:
                bot_data["interval"] = minutes
                await update.message.reply_text(f"⏱️ تم ضبط وقت التكرار إلى **{minutes} دقيقة**.")
            else:
                await update.message.reply_text("❌ يجب أن يكون الرقم أكبر من صفر.")
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")

    context.user_data["action"] = None

async def auto_post_loop(app):
    while True:
        if bot_data["is_running"] and bot_data["groups"] and bot_data["messages"]:
            for msg in bot_data["messages"]:
                if not bot_data["is_running"]:
                    break
                for group_id in bot_data["groups"]:
                    try:
                        if msg["type"] == "text":
                            await app.bot.send_message(chat_id=group_id, text=msg["text"])
                        elif msg["type"] == "photo":
                            await app.bot.send_photo(chat_id=group_id, photo=msg["file_id"], caption=msg.get("caption", ""))
                    except Exception as e:
                        print(f"خطأ في الإرسال: {e}")
                
                await asyncio.sleep(bot_data["interval"] * 60)
        else:
            await asyncio.sleep(10)

async def post_init(app):
    asyncio.create_task(auto_post_loop(app))

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_messages))

    print("البوت يعمل الآن بنجاح...")
    app.run_polling(drop_pending_updates=True)
