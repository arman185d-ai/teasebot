import logging
import random
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)
from database import db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_TARGET_ID = 1
WAITING_MESSAGE = 2
WAITING_ALLOWED_USER = 3
WAITING_INTERVAL = 4

def is_owner(user_id: int) -> bool:
    return user_id == db.get_owner_id()

def is_allowed(user_id: int, target_id: int) -> bool:
    if is_owner(user_id):
        return True
    allowed = db.get_allowed_users(target_id)
    return user_id in allowed

# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # اگه صاحب ربات نیست و خودش target هست، شوخی باهاش کن
    targets = db.get_all_targets()
    if user_id in targets and not is_owner(user_id):
        jokes = db.get_messages(user_id)
        if jokes:
            msg = random.choice(jokes)
            await update.message.reply_text(f"😈 سلام! {msg}")
        else:
            await update.message.reply_text("😈 سلام! حواست باشه من اینجام!")
        return

    if not db.get_owner_id():
        db.set_owner(user_id)
        await update.message.reply_text(
            "✅ تو به عنوان صاحب ربات ثبت شدی!\n\n"
            "از /menu برای مدیریت استفاده کن."
        )
        return

    if not is_owner(user_id):
        await update.message.reply_text("⛔ دسترسی نداری!")
        return

    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    targets = db.get_all_targets()
    keyboard = []

    for target_id in targets:
        info = db.get_target_info(target_id)
        name = info.get('name', str(target_id))
        keyboard.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"target_{target_id}")])

    keyboard.append([InlineKeyboardButton("➕ اضافه کردن هدف جدید", callback_data="add_target")])
    keyboard.append([InlineKeyboardButton("📊 آمار کلی", callback_data="stats")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🎯 *پنل مدیریت ربات شوخی‌باز*\n\nیه هدف انتخاب کن یا هدف جدید اضافه کن:"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# ─── /menu ────────────────────────────────────────────────────────────────────

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ فقط صاحب ربات می‌تونه از این دستور استفاده کنه!")
        return
    await show_main_menu(update, context)

# ─── Callbacks ────────────────────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "add_target":
        if not is_owner(user_id):
            await query.answer("⛔ دسترسی نداری!", show_alert=True)
            return
        await query.edit_message_text(
            "👤 *اضافه کردن هدف جدید*\n\n"
            "یکی از این روش‌ها رو استفاده کن:\n"
            "• آیدی متنی: `@username`\n"
            "• آیدی عددی: `123456789`\n"
            "• یه پیام از اون شخص رو فوروارد کن\n\n"
            "یا /cancel برای انصراف:",
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_TARGET_ID
        return

    if data == "stats":
        targets = db.get_all_targets()
        text = "📊 *آمار کلی*\n\n"
        for tid in targets:
            info = db.get_target_info(tid)
            msgs = db.get_messages(tid)
            text += f"👤 {info.get('name', tid)}: {len(msgs)} پیام\n"
        text += f"\nمجموع اهداف: {len(targets)}"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    if data == "back_main":
        await show_main_menu(update, context)
        return

    if data.startswith("target_"):
        target_id = int(data.split("_")[1])
        await show_target_menu(query, context, target_id, user_id)
        return

    if data.startswith("view_db_"):
        target_id = int(data.split("_")[2])
        if not is_allowed(user_id, target_id):
            await query.answer("⛔ دسترسی نداری!", show_alert=True)
            return
        messages = db.get_messages(target_id)
        if not messages:
            text = "📭 هنوز پیامی اضافه نشده!"
        else:
            text = f"📋 *پیام‌های ذخیره شده ({len(messages)} عدد):*\n\n"
            for i, msg in enumerate(messages[:20], 1):
                text += f"{i}. {msg}\n"
            if len(messages) > 20:
                text += f"\n... و {len(messages)-20} پیام دیگه"
        keyboard = [
            [InlineKeyboardButton("🗑 پاک کردن همه", callback_data=f"clear_db_{target_id}")],
            [InlineKeyboardButton("🔙 برگشت", callback_data=f"target_{target_id}")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    if data.startswith("clear_db_"):
        target_id = int(data.split("_")[2])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب ربات!", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("✅ بله، پاک کن", callback_data=f"confirm_clear_{target_id}")],
            [InlineKeyboardButton("❌ نه", callback_data=f"target_{target_id}")]
        ]
        await query.edit_message_text("⚠️ مطمئنی می‌خوای همه پیام‌ها رو پاک کنی؟",
                                       reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("confirm_clear_"):
        target_id = int(data.split("_")[2])
        db.clear_messages(target_id)
        await query.answer("✅ پیام‌ها پاک شدن!", show_alert=True)
        await show_target_menu(query, context, target_id, user_id)
        return

    if data.startswith("add_msg_"):
        target_id = int(data.split("_")[2])
        if not is_allowed(user_id, target_id):
            await query.answer("⛔ دسترسی نداری!", show_alert=True)
            return
        context.user_data['state'] = WAITING_MESSAGE
        context.user_data['target_id'] = target_id
        keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data=f"target_{target_id}")]]
        await query.edit_message_text(
            "✍️ *اضافه کردن پیام شوخی*\n\n"
            "پیام شوخی‌آمیز مورد نظرت رو بنویس:\n"
            "(می‌تونی چند پیام پشت هم بفرستی)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    if data.startswith("add_user_"):
        target_id = int(data.split("_")[2])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب ربات!", show_alert=True)
            return
        context.user_data['state'] = WAITING_ALLOWED_USER
        context.user_data['target_id'] = target_id
        allowed = db.get_allowed_users(target_id)
        text = "👥 *مدیریت افراد مجاز*\n\n"
        if allowed:
            text += "افراد فعلی:\n"
            for uid in allowed:
                text += f"• `{uid}`\n"
        else:
            text += "هنوز کسی اضافه نشده.\n"
        text += "\nآیدی عددی کاربر مجاز رو بفرست:"
        keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data=f"target_{target_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    if data.startswith("set_interval_"):
        target_id = int(data.split("_")[2])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب ربات!", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("🔴 غیرفعال", callback_data=f"interval_{target_id}_0")],
            [InlineKeyboardButton("💬 هر پیام", callback_data=f"interval_{target_id}_every")],
            [InlineKeyboardButton("⏰ هر ۳۰ دقیقه", callback_data=f"interval_{target_id}_30")],
            [InlineKeyboardButton("⏰ هر ۱ ساعت", callback_data=f"interval_{target_id}_60")],
            [InlineKeyboardButton("⏰ هر ۳ ساعت", callback_data=f"interval_{target_id}_180")],
            [InlineKeyboardButton("⏰ هر ۶ ساعت", callback_data=f"interval_{target_id}_360")],
            [InlineKeyboardButton("🔙 برگشت", callback_data=f"target_{target_id}")]
        ]
        current = db.get_interval(target_id)
        text = f"⏱ *تنظیم زمان ریپلای*\n\nحالت فعلی: `{format_interval(current)}`\n\nیه حالت انتخاب کن:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    if data.startswith("interval_"):
        parts = data.split("_")
        target_id = int(parts[1])
        interval = parts[2]
        db.set_interval(target_id, interval)
        await query.answer(f"✅ زمان‌بندی تنظیم شد!", show_alert=True)
        await show_target_menu(query, context, target_id, user_id)
        return

    if data.startswith("toggle_"):
        target_id = int(data.split("_")[1])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب ربات!", show_alert=True)
            return
        current = db.get_target_info(target_id).get('active', True)
        db.set_target_active(target_id, not current)
        status = "✅ فعال" if not current else "⏸ غیرفعال"
        await query.answer(f"وضعیت: {status}", show_alert=True)
        await show_target_menu(query, context, target_id, user_id)
        return

    if data.startswith("delete_target_"):
        target_id = int(data.split("_")[2])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب ربات!", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"confirm_del_{target_id}")],
            [InlineKeyboardButton("❌ نه", callback_data=f"target_{target_id}")]
        ]
        await query.edit_message_text("⚠️ مطمئنی می‌خوای این هدف رو حذف کنی؟",
                                       reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("confirm_del_"):
        target_id = int(data.split("_")[2])
        db.delete_target(target_id)
        await query.answer("✅ هدف حذف شد!", show_alert=True)
        await show_main_menu(update, context)
        return

async def show_target_menu(query, context, target_id: int, user_id: int):
    info = db.get_target_info(target_id)
    name = info.get('name', str(target_id))
    active = info.get('active', True)
    interval = db.get_interval(target_id)
    msgs_count = len(db.get_messages(target_id))
    allowed_count = len(db.get_allowed_users(target_id))

    status_icon = "✅" if active else "⏸"
    text = (
        f"👤 *هدف: {name}*\n"
        f"🆔 آیدی: `{target_id}`\n"
        f"📊 پیام‌ها: {msgs_count} عدد\n"
        f"👥 افراد مجاز: {allowed_count} نفر\n"
        f"⏱ حالت ریپلای: {format_interval(interval)}\n"
        f"وضعیت: {status_icon} {'فعال' if active else 'غیرفعال'}"
    )

    keyboard = [
        [InlineKeyboardButton("📋 دیدن پیام‌های ذخیره شده", callback_data=f"view_db_{target_id}")],
        [InlineKeyboardButton("✍️ اضافه کردن پیام", callback_data=f"add_msg_{target_id}")],
    ]

    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👥 افراد مجاز", callback_data=f"add_user_{target_id}")])
        keyboard.append([InlineKeyboardButton("⏱ تنظیم زمان ریپلای", callback_data=f"set_interval_{target_id}")])
        toggle_text = "⏸ غیرفعال کن" if active else "▶️ فعال کن"
        keyboard.append([InlineKeyboardButton(toggle_text, callback_data=f"toggle_{target_id}")])
        keyboard.append([InlineKeyboardButton("🗑 حذف این هدف", callback_data=f"delete_target_{target_id}")])

    keyboard.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="back_main")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

def format_interval(interval):
    if interval == "0" or interval is None:
        return "غیرفعال"
    if interval == "every":
        return "هر پیام"
    try:
        mins = int(interval)
        if mins < 60:
            return f"هر {mins} دقیقه"
        return f"هر {mins//60} ساعت"
    except:
        return str(interval)

# ─── Message handlers ─────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    state = context.user_data.get('state')

    # Handle states
    if state == WAITING_TARGET_ID and is_owner(user_id):
        await handle_add_target(update, context)
        return

    if state == WAITING_MESSAGE:
        target_id = context.user_data.get('target_id')
        if target_id and is_allowed(user_id, target_id):
            text = update.message.text
            if text and not text.startswith('/'):
                db.add_message(target_id, text)
                await update.message.reply_text(f"✅ پیام اضافه شد!\n\n`{text}`\n\nادامه بده یا /done رو بزن.", parse_mode='Markdown')
                return

    if state == WAITING_ALLOWED_USER and is_owner(user_id):
        target_id = context.user_data.get('target_id')
        text = update.message.text.strip()
        try:
            new_uid = int(text)
            db.add_allowed_user(target_id, new_uid)
            await update.message.reply_text(f"✅ کاربر `{new_uid}` به افراد مجاز اضافه شد!", parse_mode='Markdown')
            context.user_data['state'] = None
        except ValueError:
            await update.message.reply_text("❌ آیدی باید عددی باشه!")
        return

    # Handle forwarded messages for adding target
    if state == WAITING_TARGET_ID and update.message.forward_origin:
        await handle_add_target(update, context)
        return

    # Auto-reply logic
    await handle_auto_reply(update, context)

async def handle_add_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    target_id = None
    name = None

    # Forwarded message
    if msg.forward_origin:
        origin = msg.forward_origin
        if hasattr(origin, 'sender_user') and origin.sender_user:
            target_id = origin.sender_user.id
            user = origin.sender_user
            name = user.full_name or str(target_id)
        else:
            await msg.reply_text("❌ نمیشه آیدی این فوروارد رو خوند (حریم خصوصی فعاله).")
            return
    else:
        text = msg.text.strip() if msg.text else ""
        if text.startswith('@'):
            # Username - ذخیره می‌کنیم، آیدی عددی لازمه
            await msg.reply_text(
                "⚠️ برای آیدی متنی، لطفاً آیدی عددی رو بفرست.\n"
                "می‌تونی از @userinfobot آیدی عددی رو بگیری."
            )
            return
        try:
            target_id = int(text)
            name = f"هدف {target_id}"
        except ValueError:
            await msg.reply_text("❌ فرمت اشتباهه! عدد یا فوروارد بفرست.")
            return

    if target_id:
        db.add_target(target_id, name)
        context.user_data['state'] = None
        await msg.reply_text(f"✅ *{name}* (`{target_id}`) به لیست اضافه شد!", parse_mode='Markdown')
        # نشون دادن منوی هدف
        context.user_data['pending_target'] = target_id

async def handle_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    sender_id = update.message.from_user.id
    targets = db.get_all_targets()

    if sender_id not in targets:
        return

    info = db.get_target_info(sender_id)
    if not info.get('active', True):
        return

    interval = db.get_interval(sender_id)
    if interval == "0" or interval is None:
        return

    messages = db.get_messages(sender_id)
    if not messages:
        return

    should_reply = False

    if interval == "every":
        should_reply = True
    else:
        try:
            mins = int(interval)
            last_reply = db.get_last_reply_time(sender_id)
            if last_reply is None:
                should_reply = True
            else:
                elapsed = (datetime.now() - last_reply).total_seconds() / 60
                should_reply = elapsed >= mins
        except:
            should_reply = False

    if should_reply:
        chosen = random.choice(messages)
        await update.message.reply_text(f"😄 {chosen}")
        db.update_last_reply_time(sender_id)

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    context.user_data['state'] = None

    if state == WAITING_MESSAGE:
        target_id = context.user_data.get('target_id')
        count = len(db.get_messages(target_id)) if target_id else 0
        await update.message.reply_text(f"✅ تموم شد! {count} پیام ذخیره شده.")
    else:
        await update.message.reply_text("✅ عملیات لغو شد.")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    await update.message.reply_text("❌ لغو شد.")
    await show_main_menu(update, context)

# ─── /addmsg command for groups ───────────────────────────────────────────────

async def addmsg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args or len(args) < 2:
        await update.message.reply_text(
            "❌ فرمت: `/addmsg <target_id> <پیام>`\n"
            "مثال: `/addmsg 123456 چقدر امروز دیر اومدی!`",
            parse_mode='Markdown'
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ آیدی باید عددی باشه!")
        return

    if not is_allowed(user_id, target_id):
        await update.message.reply_text("⛔ دسترسی نداری!")
        return

    message = ' '.join(args[1:])
    db.add_message(target_id, message)
    await update.message.reply_text(f"✅ پیام اضافه شد!")

async def listmsg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text("❌ فرمت: `/listmsg <target_id>`", parse_mode='Markdown')
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ آیدی باید عددی باشه!")
        return

    if not is_allowed(user_id, target_id):
        await update.message.reply_text("⛔ دسترسی نداری!")
        return

    messages = db.get_messages(target_id)
    if not messages:
        await update.message.reply_text("📭 هیچ پیامی نیست!")
        return

    text = f"📋 پیام‌های ذخیره شده ({len(messages)} عدد):\n\n"
    for i, msg in enumerate(messages[:15], 1):
        text += f"{i}. {msg}\n"
    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ فقط صاحب ربات!")
        return
    targets = db.get_all_targets()
    text = "📊 *وضعیت کلی ربات*\n\n"
    for tid in targets:
        info = db.get_target_info(tid)
        msgs = db.get_messages(tid)
        interval = db.get_interval(tid)
        active = "✅" if info.get('active', True) else "⏸"
        text += f"{active} *{info.get('name', tid)}*\n"
        text += f"   پیام: {len(msgs)} | زمان: {format_interval(interval)}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

def main():
    import os
    token = os.environ.get('BOT_TOKEN')
    if not token:
        raise ValueError("BOT_TOKEN environment variable not set!")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("addmsg", addmsg_command))
    app.add_handler(CommandHandler("listmsg", listmsg_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
