import logging
import random
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from database import db

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

WAITING_TARGET_ID = "waiting_target_id"
WAITING_MESSAGE = "waiting_message"
WAITING_ALLOWED_USER = "waiting_allowed_user"

def is_owner(user_id):
    return user_id == db.get_owner_id()

def is_allowed(user_id, target_id):
    if is_owner(user_id): return True
    return user_id in db.get_allowed_users(target_id)

def format_interval(interval):
    if interval == "0" or interval is None: return "غیرفعال 🔴"
    if interval == "every": return "هر پیام 💬"
    try:
        mins = int(interval)
        return f"هر {mins} دقیقه ⏰" if mins < 60 else f"هر {mins//60} ساعت ⏰"
    except: return str(interval)

async def start(update, context):
    user_id = update.effective_user.id
    targets = db.get_all_targets()
    if user_id in targets and not is_owner(user_id):
        jokes = db.get_messages(user_id)
        msg = random.choice(jokes) if jokes else "حواست باشه من اینجام!"
        await update.message.reply_text(f"😈 سلام! {msg}")
        return
    if not db.get_owner_id():
        db.set_owner(user_id)
        await update.message.reply_text("✅ تو به عنوان صاحب ربات ثبت شدی!\n\nاز /menu برای مدیریت استفاده کن.")
        return
    if not is_owner(user_id):
        await update.message.reply_text("⛔ دسترسی نداری!")
        return
    await show_main_menu(update, context)

async def menu_command(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ فقط صاحب ربات!")
        return
    await show_main_menu(update, context)

async def show_main_menu(update, context):
    targets = db.get_all_targets()
    keyboard = []
    for tid in targets:
        info = db.get_target_info(tid)
        name = info.get('name', str(tid))
        icon = "✅" if info.get('active', True) else "⏸"
        keyboard.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"target_{tid}")])
    keyboard.append([InlineKeyboardButton("➕ اضافه کردن هدف جدید", callback_data="add_target")])
    keyboard.append([InlineKeyboardButton("📊 آمار کلی", callback_data="stats")])
    text = "🎯 *پنل مدیریت ربات شوخی‌باز*\n\nیه هدف انتخاب کن:"
    markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')

async def show_target_menu(query, context, target_id, user_id):
    info = db.get_target_info(target_id)
    name = info.get('name', str(target_id))
    active = info.get('active', True)
    interval = db.get_interval(target_id)
    msgs_count = len(db.get_messages(target_id))
    allowed_count = len(db.get_allowed_users(target_id))
    text = (f"👤 *هدف: {name}*\n🆔 آیدی: `{target_id}`\n📊 پیام‌ها: {msgs_count}\n"
            f"👥 افراد مجاز: {allowed_count}\n⏱ ریپلای: {format_interval(interval)}\n"
            f"وضعیت: {'✅ فعال' if active else '⏸ غیرفعال'}")
    keyboard = [
        [InlineKeyboardButton("📋 پیام‌های ذخیره شده", callback_data=f"view_db_{target_id}")],
        [InlineKeyboardButton("✍️ اضافه کردن پیام", callback_data=f"add_msg_{target_id}")],
    ]
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👥 افراد مجاز", callback_data=f"add_user_{target_id}")])
        keyboard.append([InlineKeyboardButton("⏱ تنظیم زمان ریپلای", callback_data=f"set_interval_{target_id}")])
        toggle = "⏸ غیرفعال کن" if active else "▶️ فعال کن"
        keyboard.append([InlineKeyboardButton(toggle, callback_data=f"toggle_{target_id}")])
        keyboard.append([InlineKeyboardButton("🗑 حذف این هدف", callback_data=f"delete_target_{target_id}")])
    keyboard.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="back_main")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "back_main":
        await show_main_menu(update, context); return

    if data == "add_target":
        if not is_owner(user_id):
            await query.answer("⛔ دسترسی نداری!", show_alert=True); return
        context.user_data['state'] = WAITING_TARGET_ID
        await query.edit_message_text(
            "👤 *اضافه کردن هدف*\n\nآیدی عددی بفرست یا پیامشو فوروارد کن:\n\n/cancel برای انصراف",
            parse_mode='Markdown'); return

    if data == "stats":
        targets = db.get_all_targets()
        text = "📊 *آمار کلی*\n\n"
        for tid in targets:
            info = db.get_target_info(tid)
            icon = "✅" if info.get('active', True) else "⏸"
            text += f"{icon} *{info.get('name', tid)}*: {len(db.get_messages(tid))} پیام\n"
        text += f"\nمجموع: {len(targets)} هدف"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]), parse_mode='Markdown'); return

    if data.startswith("target_"):
        await show_target_menu(query, context, int(data.split("_")[1]), user_id); return

    if data.startswith("view_db_"):
        target_id = int(data.split("_")[2])
        if not is_allowed(user_id, target_id):
            await query.answer("⛔ دسترسی نداری!", show_alert=True); return
        messages = db.get_messages(target_id)
        text = "📭 هنوز پیامی نیست!" if not messages else \
               f"📋 *پیام‌ها ({len(messages)}):*\n\n" + "\n".join(f"{i+1}. {m}" for i,m in enumerate(messages[:20]))
        keyboard = [[InlineKeyboardButton("🗑 پاک کردن همه", callback_data=f"clear_db_{target_id}")],
                    [InlineKeyboardButton("🔙 برگشت", callback_data=f"target_{target_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'); return

    if data.startswith("clear_db_"):
        target_id = int(data.split("_")[2])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب!", show_alert=True); return
        keyboard = [[InlineKeyboardButton("✅ بله", callback_data=f"confirm_clear_{target_id}")],
                    [InlineKeyboardButton("❌ نه", callback_data=f"target_{target_id}")]]
        await query.edit_message_text("⚠️ مطمئنی؟", reply_markup=InlineKeyboardMarkup(keyboard)); return

    if data.startswith("confirm_clear_"):
        target_id = int(data.split("_")[2])
        db.clear_messages(target_id)
        await query.answer("✅ پاک شد!", show_alert=True)
        await show_target_menu(query, context, target_id, user_id); return

    if data.startswith("add_msg_"):
        target_id = int(data.split("_")[2])
        if not is_allowed(user_id, target_id):
            await query.answer("⛔ دسترسی نداری!", show_alert=True); return
        context.user_data['state'] = WAITING_MESSAGE
        context.user_data['target_id'] = target_id
        await query.edit_message_text(
            "✍️ *اضافه کردن پیام شوخی*\n\nپیام‌هات رو بفرست، وقتی تموم شد /done بزن:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تموم شد", callback_data=f"target_{target_id}")]]),
            parse_mode='Markdown'); return

    if data.startswith("add_user_"):
        target_id = int(data.split("_")[2])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب!", show_alert=True); return
        context.user_data['state'] = WAITING_ALLOWED_USER
        context.user_data['target_id'] = target_id
        allowed = db.get_allowed_users(target_id)
        text = "👥 *افراد مجاز*\n\n"
        text += ("افراد فعلی:\n" + "\n".join(f"• `{u}`" for u in allowed) + "\n\n") if allowed else "هنوز کسی نیست.\n\n"
        text += "آیدی عددی کاربر جدید رو بفرست:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data=f"target_{target_id}")]]), parse_mode='Markdown'); return

    if data.startswith("set_interval_"):
        target_id = int(data.split("_")[2])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب!", show_alert=True); return
        current = db.get_interval(target_id)
        keyboard = [
            [InlineKeyboardButton("🔴 غیرفعال", callback_data=f"interval_{target_id}_0")],
            [InlineKeyboardButton("💬 هر پیام", callback_data=f"interval_{target_id}_every")],
            [InlineKeyboardButton("⏰ هر ۳۰ دقیقه", callback_data=f"interval_{target_id}_30")],
            [InlineKeyboardButton("⏰ هر ۱ ساعت", callback_data=f"interval_{target_id}_60")],
            [InlineKeyboardButton("⏰ هر ۳ ساعت", callback_data=f"interval_{target_id}_180")],
            [InlineKeyboardButton("⏰ هر ۶ ساعت", callback_data=f"interval_{target_id}_360")],
            [InlineKeyboardButton("🔙 برگشت", callback_data=f"target_{target_id}")]
        ]
        await query.edit_message_text(f"⏱ *تنظیم زمان ریپلای*\n\nحالت فعلی: {format_interval(current)}",
                                       reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'); return

    if data.startswith("interval_"):
        parts = data.split("_")
        target_id = int(parts[1])
        db.set_interval(target_id, parts[2])
        await query.answer("✅ تنظیم شد!", show_alert=True)
        await show_target_menu(query, context, target_id, user_id); return

    if data.startswith("toggle_"):
        target_id = int(data.split("_")[1])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب!", show_alert=True); return
        current = db.get_target_info(target_id).get('active', True)
        db.set_target_active(target_id, not current)
        await query.answer(f"{'✅ فعال' if not current else '⏸ غیرفعال'}", show_alert=True)
        await show_target_menu(query, context, target_id, user_id); return

    if data.startswith("delete_target_"):
        target_id = int(data.split("_")[2])
        if not is_owner(user_id):
            await query.answer("⛔ فقط صاحب!", show_alert=True); return
        keyboard = [[InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"confirm_del_{target_id}")],
                    [InlineKeyboardButton("❌ نه", callback_data=f"target_{target_id}")]]
        await query.edit_message_text("⚠️ مطمئنی می‌خوای این هدف رو حذف کنی؟", reply_markup=InlineKeyboardMarkup(keyboard)); return

    if data.startswith("confirm_del_"):
        target_id = int(data.split("_")[2])
        db.delete_target(target_id)
        await query.answer("✅ حذف شد!", show_alert=True)
        await show_main_menu(update, context); return

async def handle_message(update, context):
    if not update.message: return
    user_id = update.effective_user.id
    state = context.user_data.get('state')

    if state == WAITING_TARGET_ID and is_owner(user_id):
        msg = update.message
        target_id = name = None
        if msg.forward_origin:
            origin = msg.forward_origin
            if hasattr(origin, 'sender_user') and origin.sender_user:
                target_id = origin.sender_user.id
                name = origin.sender_user.full_name or str(target_id)
            else:
                await msg.reply_text("❌ نمیشه آیدی این فوروارد رو خوند."); return
        else:
            try:
                target_id = int(msg.text.strip())
                name = f"هدف {target_id}"
            except:
                await msg.reply_text("❌ آیدی عددی بفرست یا پیامشو فوروارد کن."); return
        if target_id:
            db.add_target(target_id, name)
            context.user_data['state'] = None
            await msg.reply_text(f"✅ *{name}* (`{target_id}`) اضافه شد!\n\nاز /menu مدیریتش کن.", parse_mode='Markdown')
        return

    if state == WAITING_MESSAGE:
        target_id = context.user_data.get('target_id')
        if target_id and is_allowed(user_id, target_id):
            text = update.message.text
            if text and not text.startswith('/'):
                db.add_message(target_id, text)
                await update.message.reply_text(f"✅ اضافه شد! (مجموع: {len(db.get_messages(target_id))})\nادامه بده یا /done بزن.")
                return

    if state == WAITING_ALLOWED_USER and is_owner(user_id):
        target_id = context.user_data.get('target_id')
        try:
            new_uid = int(update.message.text.strip())
            db.add_allowed_user(target_id, new_uid)
            await update.message.reply_text(f"✅ کاربر `{new_uid}` اضافه شد!", parse_mode='Markdown')
            context.user_data['state'] = None
        except:
            await update.message.reply_text("❌ آیدی باید عددی باشه!")
        return

    await handle_auto_reply(update, context)

async def handle_auto_reply(update, context):
    if not update.message or not update.message.from_user: return
    sender_id = update.message.from_user.id
    if sender_id not in db.get_all_targets(): return
    info = db.get_target_info(sender_id)
    if not info.get('active', True): return
    interval = db.get_interval(sender_id)
    if interval == "0" or interval is None: return
    messages = db.get_messages(sender_id)
    if not messages: return
    should_reply = False
    if interval == "every":
        should_reply = True
    else:
        try:
            mins = int(interval)
            last = db.get_last_reply_time(sender_id)
            should_reply = last is None or (datetime.now() - last).total_seconds() / 60 >= mins
        except: pass
    if should_reply:
        await update.message.reply_text(f"😄 {random.choice(messages)}")
        db.update_last_reply_time(sender_id)

async def done_command(update, context):
    context.user_data['state'] = None
    await update.message.reply_text("✅ تموم شد! از /menu برگرد.")

async def cancel_command(update, context):
    context.user_data['state'] = None
    await update.message.reply_text("❌ لغو شد.")
    if is_owner(update.effective_user.id):
        await show_main_menu(update, context)

async def addmsg_command(update, context):
    user_id = update.effective_user.id
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("فرمت: `/addmsg <target_id> <پیام>`", parse_mode='Markdown'); return
    try: target_id = int(args[0])
    except: await update.message.reply_text("❌ آیدی عددی!"); return
    if not is_allowed(user_id, target_id):
        await update.message.reply_text("⛔ دسترسی نداری!"); return
    db.add_message(target_id, ' '.join(args[1:]))
    await update.message.reply_text("✅ پیام اضافه شد!")

async def listmsg_command(update, context):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("فرمت: `/listmsg <target_id>`", parse_mode='Markdown'); return
    try: target_id = int(args[0])
    except: await update.message.reply_text("❌ آیدی عددی!"); return
    if not is_allowed(user_id, target_id):
        await update.message.reply_text("⛔ دسترسی نداری!"); return
    messages = db.get_messages(target_id)
    if not messages: await update.message.reply_text("📭 هیچ پیامی نیست!"); return
    text = f"📋 پیام‌ها ({len(messages)}):\n\n" + "\n".join(f"{i+1}. {m}" for i,m in enumerate(messages[:15]))
    await update.message.reply_text(text)

async def status_command(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ فقط صاحب ربات!"); return
    targets = db.get_all_targets()
    text = "📊 *وضعیت کلی*\n\n"
    for tid in targets:
        info = db.get_target_info(tid)
        icon = "✅" if info.get('active', True) else "⏸"
        text += f"{icon} *{info.get('name', tid)}*: {len(db.get_messages(tid))} پیام | {format_interval(db.get_interval(tid))}\n"
    if not targets: text += "هیچ هدفی نیست."
    await update.message.reply_text(text, parse_mode='Markdown')

def main():
    token = os.environ.get('BOT_TOKEN')
    if not token: raise ValueError("BOT_TOKEN not set!")
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
