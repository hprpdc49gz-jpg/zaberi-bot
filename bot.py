import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
from datetime import datetime

# === НАСТРОЙКИ (ЗАПОЛНИ СВОИМИ ДАННЫМИ) ===
BOT_TOKEN = '8222694333:AAE5-f5srDTzkT6qE_EfNzngDWlbp4ptq1c'  # Пример: '123456789:AAHd...'
CHANNEL_USERNAME = '@zaberi_offers'       # Пример: '@zaberi_offers' (публичный канал)
SHEET_ID = 'https://docs.google.com/spreadsheets/d/1pH22jCuHwIsOkEls070FZ3IJFBovGKFfgwa0jV8n5LI/edit?usp=sharing'           # Из URL таблицы

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Проверка подписки
async def check_subscription(user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status in ("member", "administrator", "creator")
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

# Сохранение пользователя
def save_user(user_id: str, username: str):
    try:
        users_sheet = sheet.worksheet("users")
        if not users_sheet.find(user_id, in_column=1):
            users_sheet.append_row([user_id, username, str(datetime.now())])
    except Exception as e:
        logging.error(f"Ошибка сохранения пользователя: {e}")

# Логирование выдачи промокода
def log_promo(user_id: str, promo_code: str, service: str):
    try:
        log_sheet = sheet.worksheet("log")
        log_sheet.append_row([str(datetime.now()), user_id, service, promo_code])
    except Exception as e:
        logging.error(f"Ошибка логирования: {e}")

# Главное меню
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or f"user{user_id}"

    save_user(user_id, username)

    if await check_subscription(int(user_id)):
        await send_promo(message)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Подписаться на канал", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")]
        ])
        await message.answer(
            "👋 Привет! Я — ZaberiBot!\n\n"
            "Чтобы получить бесплатный промокод на Steam, Wildberries, Ozon или игры — "
            "подпишись на наш канал с акциями!",
            reply_markup=kb
        )

@dp.callback_query(lambda c: c.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.edit_text("✅ Отлично! Ты подписан!\n\nВот твой промокод:", reply_markup=None)
        await send_promo(callback.message)
    else:
        await callback.answer("❌ Ты ещё не подписан. Подпишись и нажми «Проверить»!", show_alert=True)

async def send_promo(message: types.Message):
    try:
        promo_sheet = sheet.worksheet("promocodes")
        records = promo_sheet.get_all_records()

        available = [r for r in records if r.get('статус') == 'свободен']
        if not available:
            await message.answer("😔 Промокоды закончились! Загляни завтра — обновляем ежедневно.")
            return

        promo = random.choice(available)
        row_index = records.index(promo) + 2  # +2 из-за заголовка и индексации

        # Обновляем статус
        promo_sheet.update_cell(row_index, 3, 'использован')

        # Логируем
        log_promo(str(message.from_user.id), promo['промокод'], promo['сервис'])

        # Отправляем
        await message.answer(
            f"🔥 <b>Промокод на {promo['сервис']}:</b>\n\n"
            f"<code>{promo['промокод']}</code>\n\n"
            "💡 Скопируй и используй быстро — он одноразовый!\n\n"
            "Хочешь ещё? Приходи завтра или пригласи друга 😉",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка выдачи промокода: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуй позже.")

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())