import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
import json
import os
from datetime import datetime
from config import BOT_TOKEN, MANDATORY_CHANNEL, ADMIN_IDS, DATA_DIR, USERS_FILE, PRODUCTS_FILE, ORDERS_FILE, STATS_FILE

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_PHONE, WAITING_PRODUCT_ID, WAITING_ADMIN_IMAGE, WAITING_ADMIN_NAME, WAITING_ADMIN_PRICE, WAITING_ADMIN_DESC, WAITING_REJECT_REASON, WAITING_STATS_ID = range(8)

# Ma'lumotlar papkasini yaratish
os.makedirs(DATA_DIR, exist_ok=True)

# Helper funksiyalar
def load_json(filename, default=None):
    """JSON faylni yuklash"""
    if default is None:
        default = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(filename, data):
    """JSON faylga saqlash"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    """Admin ekanligini tekshirish"""
    return user_id in ADMIN_IDS

async def check_subscription(user_id, context):
    """Kanalga obuna tekshirish"""
    try:
        member = await context.bot.get_chat_member(MANDATORY_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_main_keyboard(user_id):
    """Asosiy menyu klaviaturasi"""
    buttons = [
        [KeyboardButton("🛍 Mahsulot buyurtma qilish")],
        [KeyboardButton("📦 Buyurtmalarim"), KeyboardButton("ℹ️ Ma'lumot")]
    ]
    if is_admin(user_id):
        buttons.append([KeyboardButton("👨‍💼 Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_admin_keyboard():
    """Admin panel klaviaturasi"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Mahsulot qo'shish")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("🔢 Hisob-kitob")],
        [KeyboardButton("🔙 Orqaga")]
    ], resize_keyboard=True)

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot boshlanganda ishlaydigan funksiya"""
    user = update.effective_user
    users = load_json(USERS_FILE, {})
    
    # Obuna tekshirish
    if not await check_subscription(user.id, context):
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{MANDATORY_CHANNEL[1:]}")
        ], [
            InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")
        ]])
        await update.message.reply_text(
            f"🔐 Botdan foydalanish uchun avval kanalimizga obuna bo'ling!\n\n"
            f"Kanal: {MANDATORY_CHANNEL}",
            reply_markup=keyboard
        )
        return ConversationHandler.END
    
    # Agar foydalanuvchi yangi bo'lsa
    if str(user.id) not in users:
        await update.message.reply_text(
            f"👋 Assalomu aleykum, {user.first_name}!\n\n"
            f"📱 Botdan foydalanish uchun telefon raqamingizni ulashing:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📞 Raqamni ulashish", request_contact=True)]], resize_keyboard=True)
        )
        return WAITING_PHONE
    
    # Foydalanuvchi mavjud bo'lsa
    await update.message.reply_text(
        f"🎉 Xush kelibsiz, {users[str(user.id)].get('name', user.first_name)}!\n\n"
        f"🛒 Buyurtma berish uchun mahsulot ID sini yuboring yoki menyudan tanlang:",
        reply_markup=get_main_keyboard(user.id)
    )
    return ConversationHandler.END

async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telefon raqamni qabul qilish"""
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
        f"✅ Ro'yxatdan o'tdingiz!\n\n"
        f"🛍 Mahsulot buyurtma qilish uchun mahsulot ID sini yuboring:",
        reply_markup=get_main_keyboard(user.id)
    )
    return ConversationHandler.END

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obuna tekshirish callback"""
    query = update.callback_query
    await query.answer()
    
    if await check_subscription(query.from_user.id, context):
        users = load_json(USERS_FILE, {})
        if str(query.from_user.id) not in users:
            await query.message.edit_text(
                f"✅ Obuna tasdiqlandi!\n\n"
                f"📱 Endi telefon raqamingizni ulashing:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📞 Raqamni ulashish", request_contact=True)]], resize_keyboard=True)
            )
        else:
            await query.message.edit_text(
                "✅ Obuna tasdiqlandi! Botdan foydalanishingiz mumkin.",
                reply_markup=None
            )
            await context.bot.send_message(
                query.from_user.id,
                "🛍 Mahsulot buyurtma qilish uchun mahsulot ID sini yuboring:",
                reply_markup=get_main_keyboard(query.from_user.id)
            )
    else:
        await query.answer("❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha xabarlarni qayta ishlash"""
    user = update.effective_user
    text = update.message.text
    
    users = load_json(USERS_FILE, {})
    if str(user.id) not in users:
        await start(update, context)
        return
    
    if text == "🛍 Mahsulot buyurtma qilish":
        await update.message.reply_text("🔍 Mahsulot ID sini kiriting (masalan: G1, G2, ...):")
        return WAITING_PRODUCT_ID
    
    elif text == "📦 Buyurtmalarim":
        await show_my_orders(update, context)
    
    elif text == "ℹ️ Ma'lumot":
        await show_info(update, context)
    
    elif text == "👨‍💼 Admin Panel" and is_admin(user.id):
        await update.message.reply_text(
            "👨‍💼 Admin Panel\n\n"
            "Kerakli bo'limni tanlang:",
            reply_markup=get_admin_keyboard()
        )
    
    elif text == "➕ Mahsulot qo'shish" and is_admin(user.id):
        await update.message.reply_text("📸 Mahsulot rasmini yuboring:")
        return WAITING_ADMIN_IMAGE
    
    elif text == "📊 Statistika" and is_admin(user.id):
        await show_statistics(update, context)
    
    elif text == "🔢 Hisob-kitob" and is_admin(user.id):
        await show_calculations(update, context)
    
    elif text == "🔙 Orqaga":
        await update.message.reply_text(
            "🏠 Asosiy menyu",
            reply_markup=get_main_keyboard(user.id)
        )
    
    elif text.startswith('G') and text[1:].isdigit():
        await show_product(update, context, text)
        return WAITING_PRODUCT_ID
    
    return ConversationHandler.END

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    """Mahsulot ma'lumotlarini ko'rsatish"""
    products = load_json(PRODUCTS_FILE, {})
    
    if product_id not in products:
        await update.message.reply_text("❌ Bunday ID li mahsulot topilmadi!")
        return
    
    product = products[product_id]
    
    text = (
        f"🛍 <b>{product['name']}</b>\n\n"
        f"💰 Narxi: <b>{product['price']}</b> so'm\n\n"
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
    """Buyurtma berish callback"""
    query = update.callback_query
    await query.answer()
    
    product_id = query.data.split('_')[1]
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha, tasdiqlash", callback_data=f"confirm_{product_id}"),
        InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data="cancel_order")
    ]])
    
    await query.message.reply_text(
        "❓ Buyurtmani tasdiqlaysizmi?",
        reply_markup=keyboard
    )

async def confirm_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtmani tasdiqlash"""
    query = update.callback_query
    await query.answer()
    
    product_id = query.data.split('_')[1]
    user = query.from_user
    
    # Ma'lumotlarni yuklash
    products = load_json(PRODUCTS_FILE, {})
    users = load_json(USERS_FILE, {})
    orders = load_json(ORDERS_FILE, {})
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0, 'products': {}})
    
    if product_id not in products:
        await query.message.edit_text("❌ Mahsulot topilmadi!")
        return
    
    # Buyurtma yaratish
    order_id = f"ORDER_{len(orders) + 1}"
    orders[order_id] = {
        'order_id': order_id,
        'user_id': user.id,
        'product_id': product_id,
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    }
    save_json(ORDERS_FILE, orders)
    
    # Statistika yangilash
    stats['total'] += 1
    if product_id not in stats['products']:
        stats['products'][product_id] = 0
    stats['products'][product_id] += 1
    save_json(STATS_FILE, stats)
    
    # Foydalanuvchi statistikasi
    users[str(user.id)]['orders_count'] = users[str(user.id)].get('orders_count', 0) + 1
    save_json(USERS_FILE, users)
    
    await query.message.edit_text("✅ Buyurtmangiz qabul qilindi! Admin ko'rib chiqadi.")
    
    # Adminga xabar
    product = products[product_id]
    user_info = users[str(user.id)]
    
    phone_number = user_info.get('phone', 'Nomалум')
    admin_text = (
        f"🔔 <b>Yangi buyurtma!</b>\n\n"
        f"👤 Mijoz: {user.first_name}\n"
        f"📱 Telefon: {phone_number}\n"
        f"🆔 User ID: {user.id}\n\n"
        f"🛍 Mahsulot: {product['name']}\n"
        f"💰 Narx: {product['price']} so'm\n"
        f"🆔 Mahsulot ID: {product_id}\n\n"
        f"📦 Buyurtma ID: {order_id}"
    )
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Qabul qilish", callback_data=f"accept_{order_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{order_id}")
    ]])
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id,
                photo=product['photo_id'],
                caption=admin_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except:
            pass
    
    # Bonus tekshirish
    if users[str(user.id)]['orders_count'] % 5 == 0:
        await context.bot.send_message(
            user.id,
            f"🎉 TABRIKLAYMIZ!\n\n"
            f"Siz {users[str(user.id)]['orders_count']} ta buyurtma qildingiz!\n"
            f"🎁 Siz bonus olish huquqiga ega bo'ldingiz!"
        )

async def accept_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtmani qabul qilish (admin)"""
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
        
        # Mijozga xabar
        user_id = orders[order_id]['user_id']
        await context.bot.send_message(
            user_id,
            "✅ Sizning buyurtmangiz admin tomonidan ko'rildi va qabul qilindi!\n\n"
            "📞 Tez orada siz bilan bog'lanamiz."
        )

async def reject_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtmani rad etish (admin)"""
    query = update.callback_query
    await query.answer()
    
    order_id = query.data.split('_')[1]
    context.user_data['reject_order_id'] = order_id
    
    await query.message.reply_text("📝 Rad etish sababini yozing:")
    return WAITING_REJECT_REASON

async def receive_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rad etish sababini qabul qilish"""
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
        
        await update.message.reply_text("✅ Buyurtma rad etildi!")
        
        # Mijozga xabar
        user_id = orders[order_id]['user_id']
        await context.bot.send_message(
            user_id,
            f"❌ Afsuski, buyurtmangiz rad etildi.\n\n"
            f"📝 Sabab: {reason}"
        )
    
    return ConversationHandler.END

async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtmalarni ko'rsatish"""
    user_id = update.effective_user.id
    orders = load_json(ORDERS_FILE, {})
    products = load_json(PRODUCTS_FILE, {})
    
    user_orders = [o for o in orders.values() if o['user_id'] == user_id]
    
    if not user_orders:
        await update.message.reply_text("📭 Sizda hali buyurtmalar yo'q.")
        return
    
    text = "📦 <b>Sizning buyurtmalaringiz:</b>\n\n"
    
    for order in user_orders[-10:]:  # Oxirgi 10 ta
        product = products.get(order['product_id'], {})
        status_emoji = "⏳" if order['status'] == 'pending' else "✅" if order['status'] == 'accepted' else "❌"
        status_text = "Kutilmoqda" if order['status'] == 'pending' else "Qabul qilindi" if order['status'] == 'accepted' else "Rad etildi"
        
        product_name = product.get('name', 'Noma\'lum')
        reject_reason = order.get('reject_reason', 'Noma\'lum')
        
        text += f"{status_emoji} <b>{product_name}</b>\n"
        text += f"   Status: {status_text}\n"
        if order['status'] == 'rejected':
            text += f"   Sabab: {reject_reason}\n"
        text += f"\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ma'lumot bo'limi"""
    text = (
        "ℹ️ <b>Bot haqida ma'lumot</b>\n\n"
        f"🤖 Bot: @{context.bot.username}\n"
        f"📢 Kanal: {MANDATORY_CHANNEL}\n\n"
        f"📝 <b>Qanday buyurtma berish:</b>\n"
        f"1️⃣ Mahsulot ID sini kiriting\n"
        f"2️⃣ Mahsulot ma'lumotlarini ko'ring\n"
        f"3️⃣ Buyurtma berish tugmasini bosing\n"
        f"4️⃣ Tasdiqlang\n\n"
        f"🎁 <b>Aksiya:</b> Har 5 ta buyurtmaga BONUS!\n\n"
        f"📞 Aloqa: Admin bilan bog'lanish uchun @admin"
    )
    
    await update.message.reply_text(text, parse_mode='HTML')

# Admin funksiyalar
async def receive_admin_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot rasmini qabul qilish"""
    if update.message.photo:
        context.user_data['product_photo'] = update.message.photo[-1].file_id
        await update.message.reply_text("✅ Rasm qabul qilindi!\n\n📝 Mahsulot nomini kiriting:")
        return WAITING_ADMIN_NAME
    else:
        await update.message.reply_text("❌ Iltimos, faqat rasm yuboring!")
        return WAITING_ADMIN_IMAGE

async def receive_admin_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot nomini qabul qilish"""
    context.user_data['product_name'] = update.message.text
    await update.message.reply_text("✅ Nom qabul qilindi!\n\n💰 Mahsulot narxini kiriting (faqat raqam):")
    return WAITING_ADMIN_PRICE

async def receive_admin_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot narxini qabul qilish"""
    try:
        price = int(update.message.text)
        context.user_data['product_price'] = price
        await update.message.reply_text("✅ Narx qabul qilindi!\n\n📄 Mahsulot haqida ma'lumot kiriting:")
        return WAITING_ADMIN_DESC
    except ValueError:
        await update.message.reply_text("❌ Iltimos, faqat raqam kiriting!")
        return WAITING_ADMIN_PRICE

async def receive_admin_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot tavsifini qabul qilish va saqlash"""
    description = update.message.text
    
    products = load_json(PRODUCTS_FILE, {})
    product_id = f"G{len(products) + 1}"
    
    products[product_id] = {
        'id': product_id,
        'name': context.user_data['product_name'],
        'price': context.user_data['product_price'],
        'description': description,
        'photo_id': context.user_data['product_photo'],
        'created_at': datetime.now().isoformat()
    }
    
    save_json(PRODUCTS_FILE, products)
    
    await update.message.reply_text(
        f"✅ Mahsulot muvaffaqiyatli qo'shildi!\n\n"
        f"🆔 Mahsulot ID: <b>{product_id}</b>\n"
        f"🛍 Nom: {context.user_data['product_name']}\n"
        f"💰 Narx: {context.user_data['product_price']} so'm",
        parse_mode='HTML',
        reply_markup=get_admin_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika ko'rsatish"""
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0, 'products': {}})
    products = load_json(PRODUCTS_FILE, {})
    
    text = "📊 <b>Statistika</b>\n\n"
    
    # Top mahsulotlar
    sorted_products = sorted(stats.get('products', {}).items(), key=lambda x: x[1], reverse=True)
    
    text += "🏆 <b>Top mahsulotlar:</b>\n\n"
    for i, (product_id, count) in enumerate(sorted_products[:5], 1):
        product_name = products.get(product_id, {}).get('name', 'Noma\'lum')
        text += f"{i}. {product_name} - {count} ta buyurtma\n"
    
    text += "\n💡 Mahsulot bo'yicha batafsil ma'lumot olish uchun mahsulot ID sini yuboring."
    
    await update.message.reply_text(text, parse_mode='HTML')
    return WAITING_STATS_ID

async def show_calculations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hisob-kitob ko'rsatish"""
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0})
    
    text = (
        f"🔢 <b>Hisob-kitob</b>\n\n"
        f"📥 Jami buyurtmalar: {stats['total']}\n"
        f"✅ Qabul qilingan: {stats['accepted']}\n"
        f"❌ Rad etilgan: {stats['rejected']}\n"
        f"⏳ Kutilmoqda: {stats['total'] - stats['accepted'] - stats['rejected']}\n\n"
        f"📊 Qabul qilish foizi: {(stats['accepted'] / stats['total'] * 100 if stats['total'] > 0 else 0):.1f}%"
    )
    
    await update.message.reply_text(text, parse_mode='HTML')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bekor qilish"""
    await update.message.reply_text(
        "❌ Jarayon bekor qilindi.",
        reply_markup=get_main_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END

def main():
    """Bot ishga tushirish"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WAITING_PHONE: [MessageHandler(filters.CONTACT, receive_contact)],
            WAITING_PRODUCT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            WAITING_ADMIN_IMAGE: [MessageHandler(filters.PHOTO, receive_admin_image)],
            WAITING_ADMIN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_name)],
            WAITING_ADMIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_price)],
            WAITING_ADMIN_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_desc)],
            WAITING_REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reject_reason)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_sub$"))
    application.add_handler(CallbackQueryHandler(order_callback, pattern="^order_"))
    application.add_handler(CallbackQueryHandler(confirm_order_callback, pattern="^confirm_"))
    application.add_handler(CallbackQueryHandler(accept_order_callback, pattern="^accept_"))
    application.add_handler(CallbackQueryHandler(reject_order_callback, pattern="^reject_"))
    
    print("🤖 Bot ishga tushdi!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
