import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
import json
import os
from datetime import datetime
from config import BOT_TOKEN, MANDATORY_CHANNEL, ADMIN_IDS, DATA_DIR, USERS_FILE, PRODUCTS_FILE, ORDERS_FILE, STATS_FILE

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# States
PHONE, ADD_PHOTO, ADD_NAME, ADD_PRICE, ADD_DESC, REJECT_REASON = range(6)

# Papka yaratish
os.makedirs(DATA_DIR, exist_ok=True)

# Helper funksiyalar
def load_json(filename, default=None):
    if default is None:
        default = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(MANDATORY_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("🛍 Mahsulot buyurtma qilish")],
        [KeyboardButton("📦 Buyurtmalarim"), KeyboardButton("ℹ️ Ma'lumot")]
    ]
    if is_admin(user_id):
        buttons.append([KeyboardButton("👨‍💼 Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Mahsulot qo'shish")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("🔢 Hisob-kitob")],
        [KeyboardButton("🔙 Orqaga")]
    ], resize_keyboard=True)

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_json(USERS_FILE, {})
    
    if not await check_subscription(user.id, context):
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{MANDATORY_CHANNEL[1:]}")
        ], [
            InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")
        ]])
        await update.message.reply_text(
            f"🔐 Botdan foydalanish uchun kanalga obuna bo'ling!\n\nKanal: {MANDATORY_CHANNEL}",
            reply_markup=keyboard
        )
        return ConversationHandler.END
    
    if str(user.id) not in users:
        await update.message.reply_text(
            f"👋 Assalomu aleykum, {user.first_name}!\n\n"
            f"📱 Telefon raqamingizni ulashing:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📞 Raqamni ulashish", request_contact=True)]], resize_keyboard=True)
        )
        return PHONE
    
    await update.message.reply_text(
        f"🎉 Xush kelibsiz, {users[str(user.id)].get('name', user.first_name)}!\n\n"
        f"🛒 Mahsulot ID sini yuboring yoki menyudan tanlang:",
        reply_markup=get_main_keyboard(user.id)
    )
    return ConversationHandler.END

async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user = update.effective_user
    
    users = load_json(USERS_FILE, {})
    users[str(user.id)] = {
        'user_id': user.id,
        'name': user.first_name,
        'username': user.username,
        'phone': contact.phone_number,
        'registered_at': datetime.now().isoformat(),
        'orders_count': 0
    }
    save_json(USERS_FILE, users)
    
    await update.message.reply_text(
        f"✅ Ro'yxatdan o'tdingiz!\n\n🛍 Mahsulot ID sini yuboring:",
        reply_markup=get_main_keyboard(user.id)
    )
    return ConversationHandler.END

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if await check_subscription(query.from_user.id, context):
        await query.message.edit_text("✅ Obuna tasdiqlandi!")
        await context.bot.send_message(
            query.from_user.id,
            "📱 Telefon raqamingizni ulashing:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📞 Raqamni ulashish", request_contact=True)]], resize_keyboard=True)
        )
    else:
        await query.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)

# Handle messages
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    users = load_json(USERS_FILE, {})
    if str(user.id) not in users:
        await start(update, context)
        return
    
    if text == "🛍 Mahsulot buyurtma qilish":
        await update.message.reply_text("🔍 Mahsulot ID sini kiriting (G1, G2, ...):")
    
    elif text == "📦 Buyurtmalarim":
        await show_orders(update, context)
    
    elif text == "ℹ️ Ma'lumot":
        await show_info(update, context)
    
    elif text == "👨‍💼 Admin Panel" and is_admin(user.id):
        await update.message.reply_text("👨‍💼 Admin Panel", reply_markup=get_admin_keyboard())
    
    elif text == "📊 Statistika" and is_admin(user.id):
        await show_stats(update, context)
    
    elif text == "🔢 Hisob-kitob" and is_admin(user.id):
        await show_calculations(update, context)
    
    elif text == "🔙 Orqaga":
        await update.message.reply_text("🏠 Asosiy menyu", reply_markup=get_main_keyboard(user.id))
    
    elif text.startswith('G') and len(text) > 1 and text[1:].isdigit():
        await show_product(update, context, text)

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    products = load_json(PRODUCTS_FILE, {})
    
    if product_id not in products:
        await update.message.reply_text("❌ Bunday mahsulot topilmadi!")
        return
    
    product = products[product_id]
    text = (
        f"🛍 <b>{product['name']}</b>\n\n"
        f"💰 Narxi: <b>{product['price']:,}</b> so'm\n\n"
        f"📝 Ma'lumot:\n{product['description']}\n\n"
        f"🤖 Bot: @{context.bot.username}\n"
        f"🆔 ID: {product_id}"
    )
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🛒 Buyurtma berish", callback_data=f"order_{product_id}")
    ]])
    
    await context.bot.send_photo(
        update.effective_chat.id,
        photo=product['photo_id'],
        caption=text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = query.data.split('_')[1]
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha, tasdiqlash", callback_data=f"confirm_{product_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")
    ]])
    
    await query.message.reply_text("❓ Buyurtmani tasdiqlaysizmi?", reply_markup=keyboard)

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = query.data.split('_')[1]
    user = query.from_user
    
    products = load_json(PRODUCTS_FILE, {})
    users = load_json(USERS_FILE, {})
    orders = load_json(ORDERS_FILE, {})
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0, 'products': {}})
    
    if product_id not in products:
        await query.message.edit_text("❌ Mahsulot topilmadi!")
        return
    
    order_id = f"ORDER_{len(orders) + 1}"
    orders[order_id] = {
        'order_id': order_id,
        'user_id': user.id,
        'product_id': product_id,
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    }
    save_json(ORDERS_FILE, orders)
    
    stats['total'] += 1
    if product_id not in stats['products']:
        stats['products'][product_id] = 0
    stats['products'][product_id] += 1
    save_json(STATS_FILE, stats)
    
    users[str(user.id)]['orders_count'] = users[str(user.id)].get('orders_count', 0) + 1
    save_json(USERS_FILE, users)
    
    await query.message.edit_text("✅ Buyurtmangiz qabul qilindi! Admin ko'rib chiqadi.")
    
    product = products[product_id]
    user_info = users[str(user.id)]
    phone_number = user_info.get('phone', 'Noma\'lum')
    
    admin_text = (
        f"🔔 <b>Yangi buyurtma!</b>\n\n"
        f"👤 Mijoz: {user.first_name}\n"
        f"📱 Telefon: {phone_number}\n"
        f"🆔 User ID: {user.id}\n\n"
        f"🛍 Mahsulot: {product['name']}\n"
        f"💰 Narx: {product['price']:,} so'm\n"
        f"🆔 Mahsulot ID: {product_id}\n\n"
        f"📦 Buyurtma ID: {order_id}"
    )
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Qabul qilish", callback_data=f"accept_{order_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{order_id}")
    ]])
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(admin_id, photo=product['photo_id'], caption=admin_text, parse_mode='HTML', reply_markup=keyboard)
        except:
            pass
    
    if users[str(user.id)]['orders_count'] % 5 == 0:
        await context.bot.send_message(
            user.id,
            f"🎉 TABRIKLAYMIZ!\n\nSiz {users[str(user.id)]['orders_count']} ta buyurtma qildingiz!\n🎁 Bonus olish huquqiga ega bo'ldingiz!"
        )

async def accept_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = query.data.split('_')[1]
    
    orders = load_json(ORDERS_FILE, {})
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0})
    
    if order_id in orders:
        orders[order_id]['status'] = 'accepted'
        save_json(ORDERS_FILE, orders)
        
        stats['accepted'] += 1
        save_json(STATS_FILE, stats)
        
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.reply_text("✅ Buyurtma qabul qilindi!")
        
        user_id = orders[order_id]['user_id']
        await context.bot.send_message(user_id, "✅ Buyurtmangiz qabul qilindi!\n\n📞 Tez orada siz bilan bog'lanamiz.")

async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = query.data.split('_')[1]
    
    context.user_data['reject_order_id'] = order_id
    await query.message.reply_text("📝 Rad etish sababini yozing:")
    return REJECT_REASON

async def receive_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    order_id = context.user_data.get('reject_order_id')
    
    orders = load_json(ORDERS_FILE, {})
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0})
    
    if order_id and order_id in orders:
        orders[order_id]['status'] = 'rejected'
        orders[order_id]['reject_reason'] = reason
        save_json(ORDERS_FILE, orders)
        
        stats['rejected'] += 1
        save_json(STATS_FILE, stats)
        
        await update.message.reply_text("✅ Buyurtma rad etildi!", reply_markup=get_admin_keyboard())
        
        user_id = orders[order_id]['user_id']
        await context.bot.send_message(user_id, f"❌ Buyurtmangiz rad etildi.\n\n📝 Sabab: {reason}")
    
    context.user_data.clear()
    return ConversationHandler.END

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders = load_json(ORDERS_FILE, {})
    products = load_json(PRODUCTS_FILE, {})
    
    user_orders = [o for o in orders.values() if o['user_id'] == user_id]
    
    if not user_orders:
        await update.message.reply_text("📭 Sizda hali buyurtmalar yo'q.")
        return
    
    text = "📦 <b>Sizning buyurtmalaringiz:</b>\n\n"
    
    for order in user_orders[-10:]:
        product = products.get(order['product_id'], {})
        status_emoji = "⏳" if order['status'] == 'pending' else "✅" if order['status'] == 'accepted' else "❌"
        status_text = "Kutilmoqda" if order['status'] == 'pending' else "Qabul qilindi" if order['status'] == 'accepted' else "Rad etildi"
        
        product_name = product.get('name', 'Noma\'lum')
        reject_reason = order.get('reject_reason', '')
        
        text += f"{status_emoji} <b>{product_name}</b>\n   Status: {status_text}\n"
        if order['status'] == 'rejected':
            text += f"   Sabab: {reject_reason}\n"
        text += "\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"ℹ️ <b>Bot haqida</b>\n\n"
        f"🤖 Bot: @{context.bot.username}\n"
        f"📢 Kanal: {MANDATORY_CHANNEL}\n\n"
        f"📝 <b>Qanday buyurtma berish:</b>\n"
        f"1️⃣ Mahsulot ID ni kiriting\n"
        f"2️⃣ Ma'lumotlarni ko'ring\n"
        f"3️⃣ Buyurtma bering\n"
        f"4️⃣ Tasdiqlang\n\n"
        f"🎁 <b>Aksiya:</b> Har 5 buyurtmaga BONUS!"
    )
    await update.message.reply_text(text, parse_mode='HTML')

# ADMIN - Mahsulot qo'shish
async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin emas!")
        return ConversationHandler.END
    
    context.user_data.clear()
    await update.message.reply_text("📸 Mahsulot rasmini yuboring:\n\n/cancel - Bekor qilish")
    return ADD_PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, rasm yuboring!\n\n/cancel - Bekor qilish")
        return ADD_PHOTO
    
    context.user_data['photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ Rasm qabul qilindi!\n\n📝 Mahsulot nomini kiriting:")
    return ADD_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text(f"✅ Nom: <b>{update.message.text}</b>\n\n💰 Narxini kiriting (faqat raqam):", parse_mode='HTML')
    return ADD_PRICE

async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.replace(' ', '').replace(',', ''))
        context.user_data['price'] = price
        await update.message.reply_text(f"✅ Narx: <b>{price:,}</b> so'm\n\n📄 Mahsulot haqida yozing:", parse_mode='HTML')
        return ADD_DESC
    except:
        await update.message.reply_text("❌ Faqat raqam kiriting!\n\n/cancel - Bekor qilish")
        return ADD_PRICE

async def receive_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text
    
    products = load_json(PRODUCTS_FILE, {})
    product_id = f"G{len(products) + 1}"
    
    products[product_id] = {
        'id': product_id,
        'name': context.user_data['name'],
        'price': context.user_data['price'],
        'description': description,
        'photo_id': context.user_data['photo'],
        'created_at': datetime.now().isoformat()
    }
    save_json(PRODUCTS_FILE, products)
    
    await update.message.reply_text(
        f"✅ Mahsulot qo'shildi!\n\n"
        f"🆔 ID: <b>{product_id}</b>\n"
        f"🛍 Nom: {context.user_data['name']}\n"
        f"💰 Narx: {context.user_data['price']:,} so'm",
        parse_mode='HTML',
        reply_markup=get_admin_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0, 'products': {}})
    products = load_json(PRODUCTS_FILE, {})
    
    text = "📊 <b>Statistika</b>\n\n🏆 <b>Top mahsulotlar:</b>\n\n"
    
    sorted_products = sorted(stats.get('products', {}).items(), key=lambda x: x[1], reverse=True)
    
    for i, (pid, count) in enumerate(sorted_products[:5], 1):
        pname = products.get(pid, {}).get('name', 'Noma\'lum')
        text += f"{i}. {pname} - {count} ta\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def show_calculations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0})
    
    text = (
        f"🔢 <b>Hisob-kitob</b>\n\n"
        f"📥 Jami: {stats['total']}\n"
        f"✅ Qabul: {stats['accepted']}\n"
        f"❌ Rad: {stats['rejected']}\n"
        f"⏳ Kutilmoqda: {stats['total'] - stats['accepted'] - stats['rejected']}\n\n"
        f"📊 Foiz: {(stats['accepted'] / stats['total'] * 100 if stats['total'] > 0 else 0):.1f}%"
    )
    await update.message.reply_text(text, parse_mode='HTML')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Start conversation
    start_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={PHONE: [MessageHandler(filters.CONTACT, receive_contact)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Add product conversation
    add_product_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Mahsulot qo\'shish$'), start_add_product)],
        states={
            ADD_PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, receive_photo)],
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_desc)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Reject conversation
    reject_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(reject_order, pattern='^reject_')],
        states={REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reject_reason)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(start_handler)
    app.add_handler(add_product_handler)
    app.add_handler(reject_handler)
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern='^check_sub$'))
    app.add_handler(CallbackQueryHandler(order_callback, pattern='^order_'))
    app.add_handler(CallbackQueryHandler(confirm_order, pattern='^confirm_'))
    app.add_handler(CallbackQueryHandler(accept_order, pattern='^accept_'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
