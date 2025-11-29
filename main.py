import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
import json
from datetime import datetime, timedelta
import os

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Holatlar
PHONE, ADD_PRODUCT_PHOTO, ADD_PRODUCT_NAME, ADD_PRODUCT_PRICE, ADD_PRODUCT_DESC, REJECT_REASON, BROADCAST_MESSAGE = range(7)

# Konfiguratsiya
CHANNEL_ID = "@hayotritmi07"  # O'zingizning kanalingiz
ADMIN_IDS = [7345368822]  # Admin ID larini kiriting
BOT_TOKEN = "8128930362:AAEdJrMNEJ0PHJpRR-rhCtODMfSx3N9sXSI"  # Bot tokenini kiriting

# Ma'lumotlar bazasi (JSON fayl)
class Database:
    def __init__(self):
        self.users_file = 'users.json'
        self.products_file = 'products.json'
        self.orders_file = 'orders.json'
        self.load_data()
    
    def load_data(self):
        # Foydalanuvchilar
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        else:
            self.users = {}
        
        # Mahsulotlar
        if os.path.exists(self.products_file):
            with open(self.products_file, 'r') as f:
                self.products = json.load(f)
        else:
            self.products = {}
        
        # Buyurtmalar
        if os.path.exists(self.orders_file):
            with open(self.orders_file, 'r') as f:
                self.orders = json.load(f)
        else:
            self.orders = []
    
    def save_users(self):
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2, ensure_ascii=False)
    
    def save_products(self):
        with open(self.products_file, 'w') as f:
            json.dump(self.products, f, indent=2, ensure_ascii=False)
    
    def save_orders(self):
        with open(self.orders_file, 'w') as f:
            json.dump(self.orders, f, indent=2, ensure_ascii=False)
    
    def add_user(self, user_id, phone, username, referrer_id=None):
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {
                'phone': phone,
                'username': username,
                'stars': 0,
                'referrer': referrer_id,
                'joined_date': datetime.now().isoformat()
            }
            # Referal tizimi
            if referrer_id and str(referrer_id) in self.users:
                self.users[str(referrer_id)]['stars'] = self.users[str(referrer_id)].get('stars', 0) + 1
            self.save_users()
            return True
        return False
    
    def add_product(self, photo_id, name, price, description, admin_username):
        product_id = f"G{len(self.products) + 1}"
        self.products[product_id] = {
            'photo_id': photo_id,
            'name': name,
            'price': price,
            'description': description,
            'admin_username': admin_username,
            'order_count': 0,
            'added_date': datetime.now().isoformat()
        }
        self.save_products()
        return product_id
    
    def add_order(self, user_id, product_id, phone):
        order = {
            'order_id': len(self.orders) + 1,
            'user_id': str(user_id),
            'product_id': product_id,
            'phone': phone,
            'status': 'pending',
            'date': datetime.now().isoformat(),
            'price': self.products[product_id]['price']
        }
        self.orders.append(order)
        self.save_orders()
        return order['order_id']
    
    def get_statistics(self):
        total = len(self.orders)
        accepted = len([o for o in self.orders if o['status'] == 'accepted'])
        rejected = len([o for o in self.orders if o['status'] == 'rejected'])
        return {'total': total, 'accepted': accepted, 'rejected': rejected}
    
    def get_top_products(self, limit=10):
        product_stats = {}
        for order in self.orders:
            if order['status'] == 'accepted':
                pid = order['product_id']
                if pid in product_stats:
                    product_stats[pid] += 1
                else:
                    product_stats[pid] = 1
        
        sorted_products = sorted(product_stats.items(), key=lambda x: x[1], reverse=True)
        return sorted_products[:limit]
    
    def get_weekly_sales(self):
        week_ago = datetime.now() - timedelta(days=7)
        total_sales = 0
        for order in self.orders:
            if order['status'] == 'accepted':
                order_date = datetime.fromisoformat(order['date'])
                if order_date >= week_ago:
                    total_sales += float(order['price'])
        return total_sales
    
    def get_top_referrers(self):
        referrers = [(uid, data['stars']) for uid, data in self.users.items()]
        return sorted(referrers, key=lambda x: x[1], reverse=True)[:3]

db = Database()

# Kanalni tekshirish
async def check_channel_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# /start buyrug'i
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Referal tizimi
    referrer_id = None
    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
    
    # Kanalni tekshirish
    if not await check_channel_subscription(user.id, context):
        keyboard = [[InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                    [InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")]]
        await update.message.reply_text(
            "Botdan foydalanish uchun kanalimizga obuna bo'ling:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Foydalanuvchi ro'yxatda bormi?
    if user_id not in db.users:
        # Telefon raqamini so'rash
        keyboard = [[KeyboardButton("📱 Kontaktni ulashish", request_contact=True)]]
        await update.message.reply_text(
            "Botdan foydalanish uchun telefon raqamingizni ulashing:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return PHONE
    
    # Asosiy menyu
    await show_main_menu(update, context)

# Telefon raqamini qabul qilish
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if contact:
        user_id = str(update.effective_user.id)
        referrer_id = context.user_data.get('referrer_id')
        db.add_user(user_id, contact.phone_number, update.effective_user.username, referrer_id)
        
        await update.message.reply_text("✅ Ro'yxatdan o'tdingiz!")
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Iltimos, 📱 Kontaktni ulashish tugmasini bosing!")
        return PHONE

# Asosiy menyu
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [["🛒 Mahsulot buyurtma qilish"], ["📊 Mening statistikam"]]
    
    if user_id in ADMIN_IDS:
        keyboard.append(["⚙️ Admin Panel"])
    
    await update.message.reply_text(
        "Asosiy menyu:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# Mahsulot ID yuborish
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "🛒 Mahsulot buyurtma qilish":
        await update.message.reply_text("Mahsulot ID sini yuboring (masalan: G1):")
        return
    
    elif text == "📊 Mening statistikam":
        user_stats = db.users.get(str(user_id), {})
        stars = user_stats.get('stars', 0)
        await update.message.reply_text(f"⭐ Sizning yulduzlaringiz: {stars}")
        return
    
    elif text == "⚙️ Admin Panel" and user_id in ADMIN_IDS:
        await show_admin_panel(update, context)
        return
    
    # Mahsulot ID tekshirish
    if text.startswith('G') and text[1:].isdigit():
        product_id = text
        if product_id in db.products:
            product = db.products[product_id]
            caption = f"📦 {product['name']}\n\n💰 Narxi: {product['price']} so'm\n\n📝 {product['description']}\n\n👤 Admin: @{product['admin_username']}"
            
            keyboard = [[InlineKeyboardButton("🛒 Buyurtma berish", callback_data=f"order_{product_id}")]]
            
            await context.bot.send_photo(
                chat_id=user_id,
                photo=product['photo_id'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ Bu ID bilan mahsulot topilmadi!")

# Admin panel
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["➕ Mahsulot qo'shish", "📊 Statistika"],
        ["📈 Top mahsulotlar", "👥 Top referallar"],
        ["📢 Xabar yuborish (Broadcast)", "💰 Haftalik savdo"],
        ["🔙 Orqaga"]
    ]
    await update.message.reply_text(
        "⚙️ Admin Panel:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# Mahsulot qo'shish
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    await update.message.reply_text("Mahsulot rasmini yuboring:")
    return ADD_PRODUCT_PHOTO

async def add_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['product_photo'] = photo.file_id
        await update.message.reply_text("Mahsulot nomini kiriting:")
        return ADD_PRODUCT_NAME
    else:
        await update.message.reply_text("❌ Iltimos, rasm yuboring!")
        return ADD_PRODUCT_PHOTO

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_name'] = update.message.text
    await update.message.reply_text("Mahsulot narxini kiriting (so'mda):")
    return ADD_PRODUCT_PRICE

async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['product_price'] = price
        await update.message.reply_text("Mahsulot haqida izoh yozing:")
        return ADD_PRODUCT_DESC
    except:
        await update.message.reply_text("❌ Iltimos, to'g'ri narx kiriting!")
        return ADD_PRODUCT_PRICE

async def add_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_desc'] = update.message.text
    
    # Mahsulotni qo'shish
    product_id = db.add_product(
        context.user_data['product_photo'],
        context.user_data['product_name'],
        context.user_data['product_price'],
        context.user_data['product_desc'],
        update.effective_user.username or "admin"
    )
    
    # Kanalga yuborish
    product = db.products[product_id]
    caption = f"🆕 Yangi mahsulot!\n\n📦 {product['name']}\n💰 Narxi: {product['price']} so'm\n\n📝 {product['description']}\n\n🆔 Mahsulot ID: {product_id}\n\n🚚 Yetkazib berish xizmati mavjud!\n📞 Admin: @{product['admin_username']}"
    
    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=product['photo_id'],
            caption=caption
        )
    except:
        pass
    
    await update.message.reply_text(f"✅ Mahsulot muvaffaqiyatli qo'shildi!\n🆔 Mahsulot ID: {product_id}")
    context.user_data.clear()
    return ConversationHandler.END

# Buyurtma berish
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "check_sub":
        if await check_channel_subscription(query.from_user.id, context):
            await query.message.reply_text("✅ Obuna tasdiqlandi!")
            await start(update, context)
        else:
            await query.message.reply_text("❌ Siz hali kanalga obuna bo'lmadingiz!")
    
    elif data.startswith("order_"):
        product_id = data.split("_")[1]
        keyboard = [[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{product_id}")],
                    [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]]
        await query.message.reply_text(
            "Buyurtmani tasdiqlaysizmi?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("confirm_"):
        product_id = data.split("_")[1]
        user_id = query.from_user.id
        phone = db.users[str(user_id)]['phone']
        
        order_id = db.add_order(user_id, product_id, phone)
        
        # Adminga xabar yuborish
        product = db.products[product_id]
        username = query.from_user.username if query.from_user.username else "Noma'lum"
        admin_msg = f"🆕 YANGI BUYURTMA!\n\n🆔 Buyurtma ID: {order_id}\n📦 Mahsulot: {product['name']} (ID: {product_id})\n👤 Mijoz: @{username}\n📱 Telefon: {phone}\n💰 Narx: {product['price']} so'm"
        
        keyboard = [[InlineKeyboardButton("✅ Qabul qilish", callback_data=f"accept_{order_id}"),
                     InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{order_id}")]]
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_msg,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Adminga xabar yuborishda xato: {e}")
        
        await query.edit_message_text("✅ Buyurtmangiz qabul qilindi! Tez orada admin siz bilan bog'lanadi.")
        
        # Asosiy menyuni qaytarish
        keyboard_main = [["🛒 Mahsulot buyurtma qilish"], ["📊 Mening statistikam"]]
        if user_id in ADMIN_IDS:
            keyboard_main.append(["⚙️ Admin Panel"])
        
        await context.bot.send_message(
            chat_id=user_id,
            text="Asosiy menyu:",
            reply_markup=ReplyKeyboardMarkup(keyboard_main, resize_keyboard=True)
        )
    
    elif data.startswith("accept_"):
        order_id = int(data.split("_")[1])
        order = db.orders[order_id - 1]
        order['status'] = 'accepted'
        db.save_orders()
        
        # Mijozga xabar yuborish
        await context.bot.send_message(
            chat_id=int(order['user_id']),
            text=f"✅ Buyurtmangiz tasdiqlandi!\n\n🆔 Buyurtma ID: {order_id}\n\nMahsulotingiz tez orada yetib keladi.\n🚚 Yetkazib berish xizmati mavjud!"
        )
        
        await query.message.reply_text(f"✅ Buyurtma #{order_id} qabul qilindi!")
    
    elif data.startswith("reject_"):
        order_id = int(data.split("_")[1])
        context.user_data['reject_order_id'] = order_id
        await query.message.reply_text("Rad etish sababini kiriting:")
        return REJECT_REASON

# Rad etish sababi
async def reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    order_id = context.user_data['reject_order_id']
    
    order = db.orders[order_id - 1]
    order['status'] = 'rejected'
    order['reject_reason'] = reason
    db.save_orders()
    
    # Mijozga xabar yuborish
    await context.bot.send_message(
        chat_id=int(order['user_id']),
        text=f"❌ Buyurtmangiz rad etildi.\n\n🆔 Buyurtma ID: {order_id}\n\nSabab: {reason}"
    )
    
    await update.message.reply_text(f"✅ Buyurtma #{order_id} rad etildi!")
    context.user_data.clear()
    return ConversationHandler.END

# Statistika
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    stats = db.get_statistics()
    msg = f"📊 STATISTIKA\n\n📦 Jami buyurtmalar: {stats['total']}\n✅ Qabul qilingan: {stats['accepted']}\n❌ Rad etilgan: {stats['rejected']}"
    
    await update.message.reply_text(msg)

# Top mahsulotlar
async def show_top_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    top = db.get_top_products()
    if not top:
        await update.message.reply_text("📊 Hali buyurtmalar yo'q!")
        return
    
    msg = "📈 TOP MAHSULOTLAR\n\n"
    for i, (pid, count) in enumerate(top, 1):
        product = db.products.get(pid, {})
        msg += f"{i}. {product.get('name', 'Noma\'lum')} (ID: {pid}) - {count} ta buyurtma\n"
    
    await update.message.reply_text(msg)

# Top referallar
async def show_top_referrers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    top = db.get_top_referrers()
    if not top:
        await update.message.reply_text("👥 Hali referallar yo'q!")
        return
    
    msg = "⭐ TOP REFERALLAR\n\n"
    for i, (uid, stars) in enumerate(top, 1):
        user = db.users.get(uid, {})
        username = user.get('username', 'Noma\'lum')
        msg += f"{i}. @{username} - {stars} ⭐\n"
    
    await update.message.reply_text(msg)

# Haftalik savdo
async def show_weekly_sales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    sales = db.get_weekly_sales()
    await update.message.reply_text(f"💰 Oxirgi 7 kundagi savdo: {sales:,.0f} so'm")

# Broadcast
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    await update.message.reply_text("📢 Barcha foydalanuvchilarga yuborish uchun xabar yozing:")
    return BROADCAST_MESSAGE

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    count = 0
    
    for user_id in db.users.keys():
        try:
            await context.bot.send_message(chat_id=int(user_id), text=message)
            count += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Xabar {count} ta foydalanuvchiga yuborildi!")
    return ConversationHandler.END

# Asosiy funksiya
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    
    # Mahsulot qo'shish
    add_product_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ Mahsulot qo'shish"), add_product_start)],
        states={
            ADD_PRODUCT_PHOTO: [MessageHandler(filters.PHOTO, add_product_photo)],
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            ADD_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)],
            ADD_PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_desc)],
        },
        fallbacks=[]
    )
    application.add_handler(add_product_handler)
    
    # Telefon raqami
    phone_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.CONTACT, get_phone)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, get_phone)],
        },
        fallbacks=[]
    )
    application.add_handler(phone_handler)
    
    # Rad etish
    reject_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_callback, pattern="^reject_")],
        states={
            REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reject_reason)],
        },
        fallbacks=[]
    )
    application.add_handler(reject_handler)
    
    # Broadcast
    broadcast_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📢 Xabar yuborish"), broadcast_start)],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)],
        },
        fallbacks=[]
    )
    application.add_handler(broadcast_handler)
    
    # Boshqa handlerlar
    application.add_handler(MessageHandler(filters.Regex("📊 Statistika"), show_statistics))
    application.add_handler(MessageHandler(filters.Regex("📈 Top mahsulotlar"), show_top_products))
    application.add_handler(MessageHandler(filters.Regex("👥 Top referallar"), show_top_referrers))
    application.add_handler(MessageHandler(filters.Regex("💰 Haftalik savdo"), show_weekly_sales))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Botni ishga tushirish
    application.run_polling()

if __name__ == '__main__':
    main()
