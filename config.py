"""
Bot konfiguratsiya fayli
Bu faylni o'zgartiring va o'z ma'lumotlaringizni kiriting
"""
import os

# ============================================
# BOT TOKEN
# ============================================
# Render.com uchun environment variable dan o'qiydi
# Local ishlatish uchun to'g'ridan-to'g'ri kiriting
BOT_TOKEN = os.getenv('BOT_TOKEN', '8128930362:AAEdJrMNEJ0PHJpRR-rhCtODMfSx3N9sXSI')


# ============================================
# MAJBURIY KANAL
# ============================================
MANDATORY_CHANNEL = os.getenv('MANDATORY_CHANNEL', '@hayotritmi07')


# ============================================
# ADMIN ID LARI
# ============================================
# Render da: ADMIN_IDS = 123456789,987654321 (vergul bilan)
# Local da: ADMIN_IDS = [123456789, 987654321]
admin_ids_str = os.getenv('ADMIN_IDS', '7345368822')
if ',' in admin_ids_str:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(',')]
else:
    ADMIN_IDS = [int(admin_ids_str)]


# ============================================
# MA'LUMOTLAR PAPKASI
# ============================================
DATA_DIR = "bot_data"
USERS_FILE = f"{DATA_DIR}/users.json"
PRODUCTS_FILE = f"{DATA_DIR}/products.json"
ORDERS_FILE = f"{DATA_DIR}/orders.json"
STATS_FILE = f"{DATA_DIR}/stats.json"
