from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import settings


# Main menu keyboard
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("💰 Купить сигнал"), KeyboardButton("💼 Баланс"))
    keyboard.row(KeyboardButton("📊 Статистика"), KeyboardButton("🆘 Поддержка"))
    return keyboard


# Admin menu keyboard
def get_admin_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("👥 Пользователи"), KeyboardButton("📈 Сигналы"))
    keyboard.row(KeyboardButton("📊 Статистика"), KeyboardButton("🔙 Обычное меню"))
    return keyboard


# Balance menu keyboard
def get_balance_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    return keyboard


# Packages selection keyboard
def get_packages_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)

    for package in settings.DEFAULT_PACKAGES:
        button_text = f"{package['signals_count']} шт. - {package['price']} USDT"
        keyboard.add(
            InlineKeyboardButton(
                button_text,
                callback_data=f"package_{package['id']}"
            )
        )

    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    return keyboard


# Payment confirmation keyboard
def get_payment_confirm_keyboard(invoice_url: str):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💳 Оплатить", url=invoice_url))
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="back_to_main"))
    return keyboard


# Deposit amount keyboard
def get_deposit_amounts_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    amounts = [5, 10, 20, 50, 100, 200]

    buttons = []
    for amount in amounts:
        buttons.append(
            InlineKeyboardButton(
                f"{amount} USDT",
                callback_data=f"deposit_amount_{amount}"
            )
        )

    # Add buttons in pairs
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.row(buttons[i], buttons[i + 1])
        else:
            keyboard.row(buttons[i])

    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    return keyboard


# Support menu keyboard
def get_support_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📝 Написать администратору", callback_data="contact_admin"))
    keyboard.add(InlineKeyboardButton("❓ FAQ", callback_data="faq"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    return keyboard


# Back button keyboard
def get_back_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    return keyboard


# Cancel state keyboard
def get_cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("❌ Отмена"))
    return keyboard