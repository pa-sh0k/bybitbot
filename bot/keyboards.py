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
    keyboard = [[InlineKeyboardButton(text="💳 Пополнить USDT", callback_data="deposit_usdt")],
                [InlineKeyboardButton(text="🛒 Купить сигналы", callback_data="buy_signals")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Signal purchasing menu
def get_buy_signals_menu():
    keyboard = [
        [InlineKeyboardButton(text="📦 Выбрать пакет", callback_data="select_package")],
        [InlineKeyboardButton(text="💳 Пополнить USDT", callback_data="deposit_usdt")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_balance")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Packages selection keyboard
def get_packages_keyboard():
    keyboard = []

    for package in settings.DEFAULT_PACKAGES:
        button_text = f"{package['name']} - {package['signals_count']} сигналов - {package['price']} USDT"
        keyboard = [
            [InlineKeyboardButton(text=button_text, callback_data=f"package_{package['id']}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_signals")]
                    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Payment confirmation keyboard
def get_payment_confirm_keyboard(invoice_url: str):
    keyboard = [
        [InlineKeyboardButton(text="💳 Оплатить", url=invoice_url)],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_balance")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# USDT deposit amount keyboard
def get_usdt_deposit_amounts_keyboard():
    keyboard = []
    amounts = [15, 25, 50, 100, 200]

    buttons = []
    for amount in amounts:
        buttons.append(
            InlineKeyboardButton(
                text=f"{amount} USDT",
                callback_data=f"deposit_usdt_{amount}"
            )
        )

    # Add buttons in pairs
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.append([buttons[i], buttons[i + 1]])
        else:
            keyboard.append([buttons[i]])

    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_balance")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard, row_width=2)


# Support menu keyboard
def get_support_keyboard():
    keyboard = []
    keyboard.append([InlineKeyboardButton(text="💬 Написать в поддержку", url="https://t.me/abc123")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Package purchase confirmation keyboard
def get_package_confirm_keyboard(package_id: int):
    keyboard = []
    keyboard.append([InlineKeyboardButton(text="✅ Подтвердить покупку", callback_data=f"confirm_package_{package_id}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="select_package")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Back button keyboard
def get_back_keyboard():
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Back to balance keyboard
def get_back_to_balance_keyboard():
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_balance")]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Cancel state keyboard
def get_cancel_keyboard():
    keyboard = [[KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
