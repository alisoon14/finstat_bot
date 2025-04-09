import telebot
from telebot.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
import time
import traceback
import signal
import sys
import settings
import json
import os
from datetime import datetime, timedelta

bot = telebot.TeleBot(settings.API_KEY)

EXPENSE_CATEGORIES = [
    "🍏 Продукты",
    "🍽️ Кафе и рестораны",
    "🚗 Транспорт",
    "🏠 Жилье",
    "🏥 Здоровье",
    "🎭 Развлечения",
    "✈️ Путешествия",
    "📦 Прочие расходы"
]

INCOME_CATEGORIES = [
    "💰 Зарплата",
    "🎁 Подарки",
    "🎓 Стипендия / Пенсия",
    "📥 Прочие доходы"
]

DATA_FILE = 'finance_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_or_create_user(user_id):
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = {
            "incomes": [],
            "expenses": [],
            "username": None,
            "first_name": None,
            "last_name": None,
            "created_at": datetime.now().isoformat()
        }
        save_data(data)
    return data[str(user_id)]

def update_user_data(user_id, user_data):
    data = load_data()
    data[str(user_id)] = user_data
    save_data(data)

def add_income(user_id, amount, category):
    user = get_or_create_user(user_id)
    clean_category = category.replace("📥 ", "").replace("💰 ", "").strip()
    user["incomes"].append({
        "amount": float(amount),
        "category": clean_category,
        "date": datetime.now().isoformat()
    })
    update_user_data(user_id, user)

def add_expense(user_id, amount, category):
    user = get_or_create_user(user_id)
    clean_category = category.replace("📦 ", "").replace("🍏 ", "").strip()
    user["expenses"].append({
        "amount": float(amount),
        "category": clean_category,
        "date": datetime.now().isoformat()
    })
    update_user_data(user_id, user)

def get_period_statistics(user_id, period='all'):
    user = get_or_create_user(user_id)
    now = datetime.now()
    
    def filter_by_date(items, start_date):
        return [item for item in items if datetime.fromisoformat(item["date"]) >= start_date]
    
    if period == 'week':
        start_date = now - timedelta(days=7)
        incomes = filter_by_date(user["incomes"], start_date)
        expenses = filter_by_date(user["expenses"], start_date)
    elif period == 'month':
        start_date = now - timedelta(days=30)
        incomes = filter_by_date(user["incomes"], start_date)
        expenses = filter_by_date(user["expenses"], start_date)
    elif period == 'year':
        start_date = now - timedelta(days=365)
        incomes = filter_by_date(user["incomes"], start_date)
        expenses = filter_by_date(user["expenses"], start_date)
    else:  # all time
        incomes = user["incomes"]
        expenses = user["expenses"]
    
    total_income = sum(item["amount"] for item in incomes)
    total_expense = sum(item["amount"] for item in expenses)
    balance = total_income - total_expense

    income_stats = {}
    for item in incomes:
        cat = item["category"]
        income_stats[cat] = income_stats.get(cat, 0) + item["amount"]

    expense_stats = {}
    for item in expenses:
        cat = item["category"]
        expense_stats[cat] = expense_stats.get(cat, 0) + item["amount"]

    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'income_stats': income_stats,
        'expense_stats': expense_stats,
        'income_count': len(incomes),
        'expense_count': len(expenses),
        'period': period
    }

def create_period_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("Неделя", callback_data='stat_week'),
        InlineKeyboardButton("Месяц", callback_data='stat_month')
    )
    keyboard.row(
        InlineKeyboardButton("Год", callback_data='stat_year'),
        InlineKeyboardButton("Все время", callback_data='stat_all')
    )
    return keyboard

def show_statistics_period(user_id):
    bot.send_message(
        user_id,
        "📊 Выберите период для статистики:",
        reply_markup=create_period_keyboard()
    )

def format_statistics_message(stats):
    period_name = {
        'week': 'неделю',
        'month': 'месяц',
        'year': 'год',
        'all': 'все время'
    }.get(stats['period'], 'период')
    
    expense_stats = "\n".join(
        f"• {cat}: -{amount:.2f}" 
        for cat, amount in stats['expense_stats'].items()
    )

    income_stats = "\n".join(
        f"• {cat}: +{amount:.2f}" 
        for cat, amount in stats['income_stats'].items()
    )

    return (
        f"📊 *Статистика за {period_name}*\n\n"
        f"*Общий доход*: +{stats['total_income']:.2f}\n"
        f"*Общий расход*: -{stats['total_expense']:.2f}\n"
        f"*Баланс*: {stats['balance']:.2f}\n\n"
        "📈 *Доходы по категориям*:\n" + income_stats + "\n\n"
        "📉 *Расходы по категориям*:\n" + expense_stats + "\n\n"
        f"Всего операций: {stats['income_count'] + stats['expense_count']}"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('stat_'))
def handle_stat_period(call):
    user_id = call.from_user.id
    period = call.data.split('_')[1]  # week, month, year, all
    
    stats = get_period_statistics(user_id, period)
    message = format_statistics_message(stats)
    
    bot.edit_message_text(
        chat_id=user_id,
        message_id=call.message.message_id,
        text=message,
        parse_mode="Markdown"
    )

def create_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Добавить доход", "Добавить расход")
    keyboard.row("Статистика")
    return keyboard

def create_expense_categories_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(*EXPENSE_CATEGORIES)
    return keyboard

def create_income_categories_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(*INCOME_CATEGORIES)
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    user_data = get_or_create_user(user.id)

    if not user_data.get("username"):
        user_data["username"] = user.username
        user_data["first_name"] = user.first_name
        user_data["last_name"] = user.last_name
        update_user_data(user.id, user_data)
    
    bot.send_message(
        user.id,
        "💰 *Трекер финансов*\n\nВыберите действие:",
        reply_markup=create_main_keyboard(),
        parse_mode="Markdown"
    )

def process_income_category_step(message):
    user_id = message.from_user.id
    category = message.text
    
    if category not in INCOME_CATEGORIES:
        bot.send_message(
            user_id,
            "❌ Неверная категория. Пожалуйста, выберите из предложенных.",
            reply_markup=create_income_categories_keyboard()
        )
        bot.register_next_step_handler(message, process_income_category_step)
        return
    
    msg = bot.send_message(
        user_id,
        f"Введите сумму дохода ({category}):",
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, lambda m: process_income_amount_step(m, category))

def process_income_amount_step(message, category):
    try:
        amount = float(message.text)
        user_id = message.from_user.id
        
        add_income(user_id, amount, category)
        
        bot.send_message(
            user_id,
            f"✅ Доход +{amount} ({category}) добавлен!",
            reply_markup=create_main_keyboard()
        )
            
    except ValueError:
        msg = bot.send_message(user_id, "❌ Ошибка! Введите число.")
        bot.register_next_step_handler(msg, lambda m: process_income_amount_step(m, category))

def process_expense_category_step(message):
    user_id = message.from_user.id
    category = message.text
    
    if category not in EXPENSE_CATEGORIES:
        bot.send_message(
            user_id,
            "❌ Неверная категория. Пожалуйста, выберите из предложенных.",
            reply_markup=create_expense_categories_keyboard()
        )
        bot.register_next_step_handler(message, process_expense_category_step)
        return
    
    msg = bot.send_message(
        user_id,
        f"Введите сумму расхода ({category}):",
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, lambda m: process_expense_amount_step(m, category))

def process_expense_amount_step(message, category):
    try:
        amount = float(message.text)
        user_id = message.from_user.id
        
        add_expense(user_id, amount, category)
        
        bot.send_message(
            user_id,
            f"✅ Расход -{amount} ({category}) добавлен!",
            reply_markup=create_main_keyboard()
        )
            
    except ValueError:
        msg = bot.send_message(user_id, "❌ Ошибка! Введите число.")
        bot.register_next_step_handler(msg, lambda m: process_expense_amount_step(m, category))

@bot.message_handler(func=lambda message: message.text == "Статистика")
def handle_statistics(message):
    show_statistics_period(message.from_user.id)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Добавить доход":
        msg = bot.send_message(
            user_id, 
            "Выберите категорию дохода:", 
            reply_markup=create_income_categories_keyboard()
        )
        bot.register_next_step_handler(msg, process_income_category_step)
    
    elif text == "Добавить расход":
        msg = bot.send_message(
            user_id, 
            "Выберите категорию расхода:", 
            reply_markup=create_expense_categories_keyboard()
        )
        bot.register_next_step_handler(msg, process_expense_category_step)
    
    elif text in EXPENSE_CATEGORIES or text in INCOME_CATEGORIES:
        bot.send_message(
            user_id,
            "Пожалуйста, сначала выберите 'Добавить доход' или 'Добавить расход'",
            reply_markup=create_main_keyboard()
        )

def signal_handler(sig, frame):
    print("\nБот остановлен")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print("Бот запущен...")

    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"Ошибка: {e}\n{traceback.format_exc()}")
            time.sleep(5)