from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from config import settings


# Main menu keyboard
def get_main_menu():
    keyboard = [
        [KeyboardButton(text="💰 Купить сигнал"), KeyboardButton(text="💼 Баланс")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🆘 Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# Admin menu keyboard
def get_admin_menu():
    keyboard = [
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="📈 Сигналы")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔙 Обычное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# Balance menu keyboard
def get_balance_menu():
    keyboard = [
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Packages selection keyboard
def get_packages_keyboard():
    keyboard = []

    for package in settings.DEFAULT_PACKAGES:
        button_text = f"{package['signals_count']} шт. - {package['price']} USDT"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"package_{package['id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Payment confirmation keyboard
def get_payment_confirm_keyboard(invoice_url: str):
    keyboard = [
        [InlineKeyboardButton(text="💳 Оплатить", url=invoice_url)],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Deposit amount keyboard
def get_deposit_amounts_keyboard():
    amounts = [5, 10, 20, 50, 100, 200]
    keyboard = []

    # Add buttons in pairs
    for i in range(0, len(amounts), 2):
        row = []
        row.append(InlineKeyboardButton(
            text=f"{amounts[i]} USDT",
            callback_data=f"deposit_amount_{amounts[i]}"
        ))

        if i + 1 < len(amounts):
            row.append(InlineKeyboardButton(
                text=f"{amounts[i + 1]} USDT",
                callback_data=f"deposit_amount_{amounts[i + 1]}"
            ))

        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Support menu keyboard
def get_support_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="📝 Написать администратору", callback_data="contact_admin")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Back button keyboard
def get_back_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Cancel state keyboard
def get_cancel_keyboard():
    keyboard = [
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)