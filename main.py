import telebot
from telebot.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
import time
import traceback
import signal
import sys
import settings

bot = telebot.TeleBot(settings.API_KEY)

user_data = {}

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

def get_or_create_user(user_id):
    """Создает запись пользователя, если ее нет"""
    if user_id not in user_data:
        user_data[user_id] = {
            "incomes": [],
            "expenses": [],
            "temp_income_category": None,
            "temp_expense_category": None
        }
    return user_data[user_id]

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
    user_id = message.from_user.id
    user = get_or_create_user(user_id) 
    
    bot.send_message(
        user_id,
        "💰 *Трекер финансов*\n\nВыберите действие:",
        reply_markup=create_main_keyboard(),
        parse_mode="Markdown"
    )

def process_income_category_step(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id)
    category = message.text
    
    if category not in INCOME_CATEGORIES:
        bot.send_message(
            user_id,
            "❌ Неверная категория. Пожалуйста, выберите из предложенных.",
            reply_markup=create_income_categories_keyboard()
        )
        bot.register_next_step_handler(message, process_income_category_step)
        return
    
    user["temp_income_category"] = category
    msg = bot.send_message(
        user_id,
        f"Введите сумму дохода ({category}):",
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, process_income_amount_step)

def process_income_amount_step(message):
    try:
        amount = float(message.text)
        user_id = message.from_user.id
        user = get_or_create_user(user_id)
        
        category = user.get("temp_income_category", "Прочие доходы")
        user["incomes"].append({
            "amount": amount,
            "category": category.replace("📥 ", "").replace("💰 ", "").strip(),
            "date": message.date
        })
        
        bot.send_message(
            user_id,
            f"✅ Доход +{amount} ({category}) добавлен!",
            reply_markup=create_main_keyboard()
        )
        
        if "temp_income_category" in user:
            del user["temp_income_category"]
            
    except ValueError:
        msg = bot.send_message(user_id, "❌ Ошибка! Введите число.")
        bot.register_next_step_handler(msg, process_income_amount_step)

def process_expense_category_step(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id)
    category = message.text
    
    if category not in EXPENSE_CATEGORIES:
        bot.send_message(
            user_id,
            "❌ Неверная категория. Пожалуйста, выберите из предложенных.",
            reply_markup=create_expense_categories_keyboard()
        )
        bot.register_next_step_handler(message, process_expense_category_step)
        return
    
    user["temp_expense_category"] = category
    msg = bot.send_message(
        user_id,
        f"Введите сумму расхода ({category}):",
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, process_expense_amount_step)

def process_expense_amount_step(message):
    try:
        amount = float(message.text)
        user_id = message.from_user.id
        user = get_or_create_user(user_id)  # Гарантированно получаем пользователя
        
        category = user.get("temp_expense_category", "Прочие расходы")
        user["expenses"].append({
            "amount": amount,
            "category": category.replace("📦 ", "").replace("🍏 ", "").strip(),
            "date": message.date
        })
        
        bot.send_message(
            user_id,
            f"✅ Расход -{amount} ({category}) добавлен!",
            reply_markup=create_main_keyboard()
        )
        
        if "temp_expense_category" in user:
            del user["temp_expense_category"]
            
    except ValueError:
        msg = bot.send_message(user_id, "❌ Ошибка! Введите число.")
        bot.register_next_step_handler(msg, process_expense_amount_step)

def show_statistics(user_id):
    user = get_or_create_user(user_id)
    
    incomes = user["incomes"]
    expenses = user["expenses"]
    
    total_income = sum(item["amount"] for item in incomes)
    total_expense = sum(item["amount"] for item in expenses)
    balance = total_income - total_expense

    expense_by_category = {}
    for expense in expenses:
        cat = expense["category"]
        expense_by_category[cat] = expense_by_category.get(cat, 0) + expense["amount"]

    expense_stats = "\n".join(
        f"• {cat}: -{amount:.2f}" 
        for cat, amount in expense_by_category.items()
    )

    income_by_category = {}
    for income in incomes:
        cat = income["category"]
        income_by_category[cat] = income_by_category.get(cat, 0) + income["amount"]

    income_stats = "\n".join(
        f"• {cat}: +{amount:.2f}" 
        for cat, amount in income_by_category.items()
    )

    stats = (
        "📊 *Статистика*\n\n"
        f"*Общий доход*: +{total_income:.2f}\n"
        f"*Общий расход*: -{total_expense:.2f}\n"
        f"*Баланс*: {balance:.2f}\n\n"
        "📈 *Доходы по категориям*:\n" + income_stats + "\n\n"
        "📉 *Расходы по категориям*:\n" + expense_stats + "\n\n"
        f"Всего операций: {len(incomes) + len(expenses)}"
    )
    
    bot.send_message(
        user_id, 
        stats, 
        parse_mode="Markdown", 
        reply_markup=create_main_keyboard()
    )

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
    
    elif text == "Статистика":
        show_statistics(user_id)
    
    elif text in EXPENSE_CATEGORIES or text in INCOME_CATEGORIES:
        bot.send_message(
            user_id,
            "Пожалуйста, сначала выберите 'Добавить доход' или 'Добавить расход'",
            reply_markup=create_main_keyboard()
        )

def signal_handler(sig, frame):
    print("Бот остановлен")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print("Бот запущен...")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"Ошибка: {e}\n{traceback.format_exc()}")
            time.sleep(5)