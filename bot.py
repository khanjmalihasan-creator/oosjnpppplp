import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
import sqlite3
import datetime
import pytz
import os
import sys
import random

# ============== تنظیمات از محیط ==============

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS_STR = os.getenv('ADMIN_IDS', '8131712128')
ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(',') if id.strip()]

# تنظیمات پنل از محیط
PANEL_CONFIG = {
    'base_url': os.getenv('PANEL_URL', ''),
    'username': os.getenv('PANEL_USERNAME', ''),
    'password': os.getenv('PANEL_PASSWORD', ''),
    'inbound_id': int(os.getenv('PANEL_INBOUND_ID', '1')),
}

# ============== تنظیمات اولیه ==============

# تنظیم منطقه زمانی
os.environ['TZ'] = 'Asia/Tehran'
try:
    import time
    time.tzset()
except:
    pass

TEHRAN_TZ = pytz.timezone('Asia/Tehran')

# پلن‌های فروش
PLANS = {
    '1month': {'name': '۱ ماهه', 'price': 50000, 'days': 30},
    '3months': {'name': '۳ ماهه', 'price': 120000, 'days': 90},
    '6months': {'name': '۶ ماهه', 'price': 200000, 'days': 180},
    '1year': {'name': 'یک ساله', 'price': 350000, 'days': 365}
}

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============== دیتابیس ==============

def get_db():
    # در Railway از پوشه data استفاده می‌کنیم
    db_path = '/data/vpn_shop.db' if os.path.exists('/data') else 'vpn_shop.db'
    return sqlite3.connect(db_path)

def init_db():
    with get_db() as conn:
        # جدول کاربران
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                join_date TEXT,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        
        # جدول سفارشات
        conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan TEXT,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                date TEXT,
                payment_date TEXT
            )
        ''')
        
        # جدول اکانت‌های VPN
        conn.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                config TEXT,
                expiry_date TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        conn.commit()
        logger.info("✅ دیتابیس راه‌اندازی شد")

# اجرای ساخت دیتابیس
init_db()

# ============== اتصال به پنل (اختیاری) ==============

try:
    from vpn_panel import XUIPanel
    if all([PANEL_CONFIG['base_url'], PANEL_CONFIG['username'], PANEL_CONFIG['password']]):
        vpn_panel = XUIPanel(PANEL_CONFIG)
        logger.info("✅ اتصال به پنل VPN برقرار شد")
    else:
        vpn_panel = None
        logger.warning("⚠️ اطلاعات پنل کامل نیست، کانفیگ دستی ارسال می‌شود")
except Exception as e:
    vpn_panel = None
    logger.error(f"❌ خطا در اتصال به پنل: {e}")

# ============== توابع کمکی ==============

def get_tehran_time():
    return datetime.datetime.now(TEHRAN_TZ)

def format_datetime(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# ============== توابع ربات ==============

async def start(update: Update, context):
    user = update.effective_user
    now = format_datetime(get_tehran_time())
    
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, join_date)
                VALUES (?, ?, ?, ?)
            ''', (user.id, user.username, user.first_name, now))
            
            if user.id in ADMIN_IDS:
                conn.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (user.id,))
            conn.commit()
        
        keyboard = [
            [InlineKeyboardButton("🛒 خرید VPN", callback_data='buy')],
            [InlineKeyboardButton("📋 اکانت‌های من", callback_data='my_accounts')],
            [InlineKeyboardButton("📞 پشتیبانی", callback_data='support')],
            [InlineKeyboardButton("ℹ️ درباره ما", callback_data='about')]
        ]
        
        welcome_text = f"""
🌟 به ربات فروش VPN خوش آمدید {user.first_name}!

✅ فروش اکانت با کیفیت
✅ پشتیبانی ۲۴ ساعته
✅ قیمت مناسب

لطفاً یکی از گزینه‌های زیر را انتخاب کنید:
        """
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"👤 کاربر جدید: {user.id} - {user.first_name}")
        
    except Exception as e:
        logger.error(f"❌ خطا در start: {e}")
        await update.message.reply_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == 'buy':
            await show_plans(query)
        elif query.data == 'my_accounts':
            await show_accounts(query)
        elif query.data == 'support':
            await show_support(query)
        elif query.data == 'about':
            await show_about(query)
        elif query.data.startswith('plan_'):
            await select_plan(query, context)
        elif query.data.startswith('payment_done_'):
            await payment_done(query)
        elif query.data == 'main_menu':
            await main_menu(query)
    except Exception as e:
        logger.error(f"❌ خطا در button_handler: {e}")
        await query.edit_message_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")

async def show_plans(query):
    keyboard = []
    for plan_id, plan in PLANS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{plan['name']} - {plan['price']:,} تومان",
                callback_data=f'plan_{plan_id}'
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')])
    
    await query.edit_message_text(
        "📦 پلن‌های موجود:\n\nلطفاً پلن مورد نظر خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_plan(query, context):
    plan_id = query.data.replace('plan_', '')
    plan = PLANS.get(plan_id)
    
    if not plan:
        await query.edit_message_text("❌ پلن انتخاب شده معتبر نیست!")
        return
    
    context.user_data['selected_plan'] = plan_id
    
    keyboard = [
        [InlineKeyboardButton("✅ تایید و ادامه", callback_data='confirm_payment')],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='buy')]
    ]
    
    text = f"""
📋 خلاصه سفارش:

📦 پلن: {plan['name']}
⏱ مدت: {plan['days']} روز
💰 مبلغ: {plan['price']:,} تومان

برای ادامه پرداخت، دکمه زیر را بزنید:
    """
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_payment(query, context):
    user_id = query.from_user.id
    plan_id = context.user_data.get('selected_plan')
    
    if not plan_id:
        await query.edit_message_text("❌ خطا! لطفاً دوباره از ابتدا شروع کنید.")
        return
    
    plan = PLANS[plan_id]
    now = format_datetime(get_tehran_time())
    
    with get_db() as conn:
        cur = conn.execute('''
            INSERT INTO orders (user_id, plan, amount, date, status)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
        ''', (user_id, plan_id, plan['price'], now, 'pending'))
        order_id = cur.fetchone()[0]
        conn.commit()
    
    keyboard = [
        [InlineKeyboardButton("✅ پرداخت انجام شد", callback_data=f'payment_done_{order_id}')],
        [InlineKeyboardButton("🔙 انصراف", callback_data='main_menu')]
    ]
    
    text = f"""
🆔 شماره سفارش: {order_id}
💰 مبلغ قابل پرداخت: {plan['price']:,} تومان

💳 برای پرداخت به آیدی زیر مبلغ را ارسال کنید:
👤 @admin

⚠️ بعد از واریز، دکمه "پرداخت انجام شد" را بزنید.
    """
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def payment_done(query):
    order_id = query.data.replace('payment_done_', '')
    user_id = query.from_user.id
    
    with get_db() as conn:
        order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
        if order:
            conn.execute('UPDATE orders SET status = ?, payment_date = ? WHERE id = ?', 
                        ('paid', format_datetime(get_tehran_time()), order_id))
            conn.commit()
    
    if order:
        plan_id = order[2]
        plan = PLANS.get(plan_id)
        
        # ساخت کانفیگ تستی (اگه پنل نداری)
        test_config = f"vless://test@{query.from_user.id}.com:443?path=%2F&security=tls&encryption=none&type=ws#{query.from_user.first_name}"
        
        with get_db() as conn:
            expiry = get_tehran_time() + datetime.timedelta(days=plan['days'])
            conn.execute('''
                INSERT INTO accounts (user_id, config, expiry_date)
                VALUES (?, ?, ?)
            ''', (user_id, test_config, format_datetime(expiry)))
            conn.commit()
        
        text = f"""
✅ **پرداخت با موفقیت تایید شد!**

🆔 شماره سفارش: {order_id}
📦 پلن: {plan['name']}

🔗 **کانفیگ شما:**
`{test_config}`

📅 تاریخ انقضا: {(get_tehran_time() + datetime.timedelta(days=plan['days'])).strftime('%Y/%m/%d')}

⚠️ این کانفیگ مخصوص شماست، به هیچ کس ندهید!
        """
    else:
        text = "❌ سفارش یافت نشد!"
    
    keyboard = [[InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_accounts(query):
    user_id = query.from_user.id
    
    with get_db() as conn:
        accounts = conn.execute('''
            SELECT * FROM accounts 
            WHERE user_id = ? AND is_active = 1
            ORDER BY expiry_date DESC
        ''', (user_id,)).fetchall()
    
    if not accounts:
        text = "📭 شما هیچ اکانت فعالی ندارید.\nبرای خرید به بخش خرید بروید."
    else:
        text = "📋 اکانت‌های فعال شما:\n\n"
        for acc in accounts:
            try:
                expiry = datetime.datetime.strptime(acc[3], "%Y-%m-%d %H:%M:%S")
                now = get_tehran_time()
                remaining = (expiry - now).days
                text += f"🔹 کانفیگ:\n"
                text += f"   📅 تاریخ انقضا: {expiry.strftime('%Y/%m/%d')}\n"
                text += f"   ⏳ روزهای باقی‌مانده: {remaining}\n"
                text += f"   🔗 کانفیگ: `{acc[2]}`\n\n"
            except:
                text += f"🔹 کانفیگ: `{acc[2]}`\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_support(query):
    text = """
📞 **پشتیبانی:**

👤 آیدی تلگرام: @admin
📧 ایمیل: support@example.com

⏰ ساعات پاسخگویی: ۹ صبح تا ۱۲ شب
    """
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_about(query):
    text = """
ℹ️ **درباره ما:**

✅ سرورهای پرسرعت
✅ پشتیبانی ۲۴ ساعته
✅ قیمت مناسب
✅ ترافیک نامحدود

نسخه: 1.0.0
    """
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def main_menu(query):
    keyboard = [
        [InlineKeyboardButton("🛒 خرید VPN", callback_data='buy')],
        [InlineKeyboardButton("📋 اکانت‌های من", callback_data='my_accounts')],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data='support')],
        [InlineKeyboardButton("ℹ️ درباره ما", callback_data='about')]
    ]
    
    await query.edit_message_text(
        "🌟 منوی اصلی:\nلطفاً یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============== اجرای اصلی ==============

def main():
    print("=" * 50)
    print("🤖 ربات تلگرام در حال راه‌اندازی...")
    print(f"🔑 توکن: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:]}")
    print("📍 برای توقف: Ctrl + C")
    print("=" * 50)
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("admin", admin_panel))
        app.add_handler(CallbackQueryHandler(button_handler))
        
        print("✅ ربات با موفقیت راه‌اندازی شد!")
        app.run_polling()
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")

if __name__ == '__main__':
    main()
