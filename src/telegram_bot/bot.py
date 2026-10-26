import asyncio
import os
import telebot
from aiohttp import web

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputFile, ReplyKeyboardMarkup, \
    KeyboardButton, ReplyKeyboardRemove
from telebot.async_telebot import AsyncTeleBot

from src.config import settings
from src.logger_config import setup_logger
from src.payments.repository import PaymentRepository
from src.telegram_bot.meneger_sending import notify_admins, notify_dev
from src.telegram_bot.models import User, ConsultationType
from src.telegram_bot.repository import TelegramBotRepository, ConsultationRepository, Validation, AdminRepository, \
    ServiceRepository, StatisticsAdmin, SupportRepository

BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
WEBHOOK_PATH = settings.WEBHOOK_PATH
WEBHOOK_URL = settings.WEBHOOK_URL_PATH

app = web.Application()
bot = AsyncTeleBot(BOT_TOKEN)
logger = setup_logger('telegram_bot', 'bot', 'bot.log')


# utilits
def get_admins_keyboard():
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("📋 Посмотреть записи", callback_data="admin_view_consultations"))
    kb.row(InlineKeyboardButton("⚙️ Настройки консультаций", callback_data="admin_paid_consultations_settings"))
    kb.row(InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    kb.row(InlineKeyboardButton("🆘 Обращения в поддержку", callback_data="admin_view_support"))
    return kb


async def show_start_menu(user: User, chat_id: int, message_id: int = None):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    keyboard.row(InlineKeyboardButton(text="📋 Мои консультации", callback_data="my_consultations"))
    keyboard.row(InlineKeyboardButton(text="✍️ Записаться", callback_data="book"))
    keyboard.row(InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"))

    text = f"Привет, {user.username}!\nТы уже зарегистрирован, выбери действие ниже 👇"

    if message_id:
        await bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)


# start
@bot.message_handler(commands=['start'])
async def start(message):
    user_id = message.from_user.id
    user = await TelegramBotRepository.get_user(user_id)
    logger.info(f"Пользователь {user_id} запустил бота")

    if not user:
        logger.info(f"Пользователь не зарегистрирован. Начало регистрации")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(text="Пройти регистрацию", callback_data="register"))
        await bot.send_message(
            chat_id=message.chat.id,
            text="Привет! 🙌\nЯ цифровой психолог. Давай сначала познакомимся.\n\nНажми кнопку ниже, чтобы начать регистрацию 👇",
            reply_markup=kb
        )
        return

    logger.info(f"Пользователь зарегистрирован. Показ меню")
    await show_start_menu(user, message.chat.id)


# admin logic (без изменений)
create_service_data = {}
edit_service_data = {}
admin_voice_data = {}


async def show_create_service_confirm(user_id: int):
    data = create_service_data[user_id]
    type_label = "🎯 Донат" if data.get("is_donat") else "📌 Обычная"
    price_label = "Сумма на ваш выбор" if data.get("is_donat") else f"{data['price']} ₽"
    text = f"📋 Проверьте данные:\n\n📌 Тип: {type_label}\n📌 Название: {data['name']}\n📝 Описание: {data.get('description', '—')}\n💰 Цена: {price_label}\n\nВсё верно?"
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("✅ Да", callback_data="confirm_create_service"),
           InlineKeyboardButton("❌ Нет", callback_data="admin_paid_consultations_settings"))
    await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)


async def show_edit_service_confirm(user_id: int):
    data = edit_service_data[user_id]
    text = f"📋 Проверьте данные:\n\n📌 Название: {data['name']}\n💰 Цена: {data['price']} ₽\n\nВсё верно?"
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("✅ Да", callback_data="confirm_edit_service"),
           InlineKeyboardButton("❌ Нет", callback_data="admin_paid_consultations_settings"))
    await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)


@bot.message_handler(commands=['admin'])
async def admin(message):
    user_id = message.from_user.id
    if not await AdminRepository.is_admin(user_id):
        await bot.send_message(chat_id=message.chat.id, text="❌ Доступ ограничен")
    else:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🔐 Админ-панель\n\n📌 Доступные действия:\n• 📋 Просмотр всех записей\n• ⚙️ Управление консультациями\n• 📊 Статистика\n• 🆘 Обращения в поддержку\n\nВыберите действие ниже 👇"),
            reply_markup=get_admins_keyboard()
        )


@bot.callback_query_handler(func=lambda call: call.data == "admin_paid_consultations_settings")
async def admin_paid_consultations_settings(call: CallbackQuery):
    user_id = call.from_user.id
    if user_id in create_service_data: del create_service_data[user_id]
    try:
        kb = InlineKeyboardMarkup()
        paid_consultations = await ServiceRepository.get_services_list_by_admin()
        if not paid_consultations:
            text = "😕 Платных консультаций пока нет.\n\nВы можете ее добавить, нажмите на ➕ Добавить"
        else:
            text = "📋 Список консультаций:\n\n"
            for idx, con in enumerate(paid_consultations, 1):
                text += (f"{idx}. {con.name} — {con.price} ₽\n{con.description}\n\n")
        kb.add(InlineKeyboardButton("➕ Добавить", callback_data="create_service"),
               InlineKeyboardButton("🔙 Назад", callback_data="admin_back"),
               InlineKeyboardButton("🗑️ Удалить", callback_data="admin_delete_service"))
        await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=text, reply_markup=kb)
    except Exception as e:
        if "Error code: 400" in str(e): pass
        logger.error(f"Ошибка у админа {user_id}: {str(e)}")
        await bot.send_message(chat_id=call.message.chat.id, text="❌ Произошла ошибка")


@bot.callback_query_handler(func=lambda call: call.data == "admin_view_consultations")
async def admin_view_consultations(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("💳 Платные записи", callback_data="admin_view_paid"))
        kb.row(InlineKeyboardButton("🔙 Назад", callback_data="admin_back"))
        await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text="Выберите тип записей:",
                                    reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка у админа {user_id}: {str(e)}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "admin_view_paid")
async def admin_view_paid_consultations(call: CallbackQuery):
    user_id = call.from_user.id
    consultations = await ConsultationRepository.get_paid_consultations_list()
    if not consultations:
        await bot.answer_callback_query(call.id, text="📭 Платных записей пока нет.", show_alert=True)
        return
    text = "💳 Платные записи:\n\n"
    for idx, row in enumerate(consultations, 1):
        viewed_emoji = "🆕" if not row.is_viewed else "✅"
        text += (
            f"{viewed_emoji} {idx}. {row.username}\n📌 {row.service_name}\n📱 {row.phone_number}\n📅 {row.date_of_birth}\n")
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("✅ Отметить просмотренные", callback_data="admin_mark_viewed_paid"))
    kb.row(InlineKeyboardButton("🔙 Назад", callback_data="admin_view_consultations"))
    await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=text, reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data == "admin_mark_viewed_paid")
async def admin_mark_viewed(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        unviewed = await ConsultationRepository.get_unviewed_consultation_list(ConsultationType.PAID)
        if not unviewed:
            await bot.answer_callback_query(call.id, "✅ Все записи уже просмотрены!")
            await admin_view_consultations(call)
            return
        text = "🆕 **Непросмотренные записи:**\n\n"
        for idx, row in enumerate(unviewed, 1):
            text += f"{idx}. {row.username}\n📱 {row.phone_number}\n📅 {row.date_of_birth}\n\n"
        text += "\nВыберите номер записи:"
        kb = InlineKeyboardMarkup()
        row = []
        for idx, row_data in enumerate(unviewed, 1):
            row.append(InlineKeyboardButton(str(idx), callback_data=f"admin_mark_{row_data.consultation_id}"))
            if len(row) == 5:
                kb.row(*row)
                row = []
        if row: kb.row(*row)
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_view_consultations"))
        await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=text, reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка у админа {user_id}: {str(e)}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_mark_"))
async def admin_mark_single(call: CallbackQuery):
    user_id = call.from_user.id
    consultation_id = int(call.data.split("_")[-1])
    try:
        await ConsultationRepository.mark_as_viewed(consultation_id)
        await bot.answer_callback_query(call.id, "✅ Запись отмечена!")
        await admin_mark_viewed(call)
    except Exception as e:
        logger.error(f"Ошибка у админа {user_id}: {str(e)}")
        await bot.send_message(chat_id=call.message.chat.id, text="❌ Ошибка")


@bot.callback_query_handler(func=lambda call: call.data.startswith("create_service"))
async def create_service(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        create_service_data[user_id] = {}
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("📌 Обычная", callback_data="service_type_normal"),
               InlineKeyboardButton("🎯 Донат", callback_data="service_type_donat"))
        await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id,
                                    text="✏️ Выберите тип консультации:", reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка у админа {user_id}: {str(e)}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("service_type_"))
async def service_type_choice(call: CallbackQuery):
    user_id = call.from_user.id
    service_type = call.data.split("_")[-1]
    create_service_data[user_id]["is_donat"] = (service_type == "donat")
    create_service_data[user_id]["step"] = "name"
    await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id,
                                text="✏️ Введите название консультации:")


@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_service")
async def admin_delete_service_list(call: CallbackQuery):
    user_id = call.from_user.id
    services = await ServiceRepository.get_services_list()
    if not services:
        await bot.answer_callback_query(call.id, text="😕 Нет услуг для удаления", show_alert=True)
        return
    text = "🗑️ Выберите консультацию для удаления:\n\n"
    for idx, service in enumerate(services, 1):
        text += f"{idx}. {service.name} — {service.price} ₽\n"
    text += "\nВыберите номер:"
    kb = InlineKeyboardMarkup()
    row = []
    for idx, service in enumerate(services, 1):
        row.append(InlineKeyboardButton(str(idx), callback_data=f"admin_delete_service_{service.id}"))
        if len(row) == 5:
            kb.row(*row)
            row = []
    if row: kb.row(*row)
    kb.row(InlineKeyboardButton("🔙 Назад", callback_data="admin_paid_consultations_settings"))
    await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=text, reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_delete_service_"))
async def admin_delete_service_confirm(call: CallbackQuery):
    service_id = int(call.data.split("_")[-1])
    user_id = call.from_user.id
    try:
        await ServiceRepository.delete_service(service_id)
        await bot.answer_callback_query(call.id, text="✅ Услуга удалена!")
        await admin_paid_consultations_settings(call)
    except Exception as e:
        logger.error(f"Ошибка при удалении: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "confirm_create_service")
async def confirm_create_service(call: CallbackQuery):
    user_id = call.from_user.id
    data = create_service_data.get(user_id)
    try:
        if not data:
            await bot.send_message(chat_id=user_id, text="❌ Данные не найдены.")
            return
        await ServiceRepository.create_service(
            name=data["name"], price=data["price"], description=data["description"],
            is_donat=data.get("is_donat", False)
        )
        del create_service_data[user_id]
        await bot.answer_callback_query(call.id, text="✅ Консультация создана!")
        await admin_paid_consultations_settings(call)
    except Exception as e:
        logger.error(f"Ошибка при создании: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        total_paid = await StatisticsAdmin.count_paid_consultations()
        today_paid = await StatisticsAdmin.count_paid_consultations_today()
        unviewed = await StatisticsAdmin.count_unviewed()
        paid_statuses = await StatisticsAdmin.count_paid_statuses()
        total_clients = await StatisticsAdmin.count_users()

        text = f"""
📊 Статистика бота

👥 Клиенты:
• Всего клиентов: {total_clients}

📋 Консультации:
• Всего платных: {total_paid}
• За сегодня (платных): {today_paid}
• Непросмотренных: {unviewed}

💳 Статусы платных записей:
• Оплачено: {paid_statuses.get('succeeded', 0)}
• Ожидают оплаты: {paid_statuses.get('pending', 0)}
• Отменено: {paid_statuses.get('cancelled', 0)}
        """
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("🔙 Назад", callback_data="admin_back"))
        await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=text, reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "admin_view_support")
async def admin_view_support(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        support_requests = await SupportRepository.get_all_with_users()
        if not support_requests:
            await bot.answer_callback_query(call.id, text="📭 Обращений нет.", show_alert=True)
            return
        text = "🆘 Обращения в поддержку:\n\n"
        for idx, req in enumerate(support_requests, 1):
            text += (
                f"{idx}. {req.user.username} {req.user.id}\n📝 {req.message[:50]}...\n📱 {req.user.phone_number}\n📅 {req.created_at.strftime('%d.%m.%Y %H:%M')}\n\n")
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("🔙 Назад", callback_data="admin_back"))
        await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=text, reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "admin_back")
async def admin_back(call: CallbackQuery):
    user_id = call.from_user.id
    await bot.edit_message_text(
        chat_id=call.message.chat.id, message_id=call.message.message_id,
        text="🔐 Админ-панель\n\nВыберите действие ниже 👇",
        reply_markup=get_admins_keyboard()
    )


# --- РЕГИСТРАЦИЯ ---
registration_data = {}


@bot.callback_query_handler(func=lambda call: call.data == "register")
async def register(call: CallbackQuery):
    user_id = call.from_user.id
    registration_data[user_id] = {"step": "name"}
    await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                text="Давай пройдем небольшую регистрацию!")
    await bot.send_message(chat_id=call.message.chat.id,
                           text="✏️ Для начала, как тебя зовут?\n(Введите имя используя латиницу, пример: Ivan)")


@bot.callback_query_handler(func=lambda call: call.data == "confirm")
async def confirm(call: CallbackQuery):
    user_id = call.from_user.id
    data = registration_data.get(user_id)

    if not data:
        await bot.edit_message_text(text="❌ Вы не зарегистрированы. Нажмите /start", chat_id=call.message.chat.id,
                                    message_id=call.message.message_id)
        return

    try:
        logger.info(f"Регистрация для пользователя TG_ID {user_id}")

        # ✅ 1. Создаем пользователя (метод возвращает ID)
        await TelegramBotRepository.register_user(user_id, data["name"], data["birth"], data["phone"])

        # ✅ 2. ЗАНОВО БЕРЕМ ОБЪЕКТ ПОЛЬЗОВАТЕЛЯ ИЗ БД
        user = await TelegramBotRepository.get_user(user_id)

        # Удаляем Reply-клавиатуру с телефоном
        await bot.send_message(chat_id=user_id, text="✅ Регистрация успешно завершена!",
                               reply_markup=ReplyKeyboardRemove())

        del registration_data[user_id]

        # ✅ 3. ПЕРЕХОДИМ В МЕНЮ С ОБЪЕКТОМ USER
        await show_start_menu(user, call.message.chat.id)

    except Exception as e:
        logger.error(f"Ошибка при регистрации {user_id}: {str(e)}")
        await bot.send_message(chat_id=user_id, text="❌ Произошла ошибка при регистрации.")


@bot.callback_query_handler(func=lambda call: call.data == "cancel")
async def cancel(call: CallbackQuery):
    user_id = call.from_user.id
    if user_id in registration_data: del registration_data[user_id]
    registration_data[user_id] = {"step": "name"}
    await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                text="🔄 Давай попробуем ещё раз! Как тебя зовут?")


# -- ЛОГИКА ПРОФИЛЯ И МЕНЮ --
@bot.callback_query_handler(func=lambda call: call.data == "profile")
async def view_profile(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)
    try:
        kb = InlineKeyboardMarkup()
        if not user:
            await bot.edit_message_text(text="❌ Вы не зарегистрированы. /start", chat_id=call.message.chat.id,
                                        message_id=call.message.message_id)
            return
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_start"))
        await bot.edit_message_text(
            text=f"👤 Мой профиль\n\n🪪 Имя: {user.username}\n📱 Телефон: {user.phone_number}\n📅 Дата рождения: {user.date_of_birth}",
            chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb
        )
    except Exception as e:
        logger.error(f"Ошибка профиля {user_id}: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "my_consultations")
async def view_my_consultation(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)
    try:
        kb = InlineKeyboardMarkup()
        if not user:
            await bot.edit_message_text(text="❌ Вы не зарегистрированы. /start", chat_id=call.message.chat.id,
                                        message_id=call.message.message_id)
            return
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_start"))
        consultations = await ConsultationRepository.get_consultation_list_by_user(user.id)
        if not consultations:
            text = "📭 У вас пока нет записей."
        else:
            text = "📋 Мои записи:\n\n"
            for idx, row in enumerate(consultations, 1):
                viewed_emoji = "⏳ - В процессе..." if not row.is_viewed else "✅ - Пройдена"
                created_date = row.created_at.strftime("%d.%m.%Y") if row.created_at else "—"
                text += f"{idx}. {row.service_name}\n📌 Статус записи: {viewed_emoji}\n📅 Дата записи: {created_date}\n\n"
        await bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка записей {user_id}: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "book")
async def view_paid_consultation(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)
    try:
        kb = InlineKeyboardMarkup()
        paid_consultations = await ServiceRepository.get_services_list()
        if not paid_consultations:
            text = "😕 Платных консультаций пока нет."
        else:
            text = "💳 Выберите консультацию:\n\n"
            for con in paid_consultations:
                kb.row(InlineKeyboardButton(f"💬 {con.name}", callback_data=f"consult_{con.id}"))
        kb.row(InlineKeyboardButton("🔙 Назад", callback_data="back_to_start"))
        await bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка просмотра консультаций {user_id}: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("consult_"))
async def service_card(call: CallbackQuery):
    service_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    try:
        service = await ServiceRepository.get_service_by_id(service_id)
        if service.is_donat:
            text = f"🎯 {service.name}\n\n📝 {service.description or 'Описание отсутствует'}\n\n💰 Сумма на ваш выбор\n\nНажмите «Оплатить», чтобы ввести сумму и перейти к оплате."
            kb = InlineKeyboardMarkup()
            kb.row(InlineKeyboardButton("💳 Оплатить", callback_data=f"donat_pay_{service_id}"))
            kb.row(InlineKeyboardButton("🔙 Назад", callback_data="book"))
        else:
            text = f"📌 {service.name}\n\n📝 Описание: {service.description or '—'}\n\n💰 Цена: {service.price} ₽\n\nНажмите «Оплатить», чтобы перейти к оплате."
            kb = InlineKeyboardMarkup()
            kb.row(InlineKeyboardButton(f"💳 Оплатить {service.price} ₽", callback_data=f"pay_{service_id}"))
            kb.row(InlineKeyboardButton("🔙 Назад", callback_data="book"))
        await bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=text, reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка карточки: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
async def process_payment(call: CallbackQuery):
    service_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)
    try:
        service = await ServiceRepository.get_service_by_id(service_id)
        link = await PaymentRepository.create_payment_link(amount=service.price,
                                                           desc=f"Оплата консультации: {service.name}", user_id=user_id,
                                                           service_id=service_id)
        await PaymentRepository.save_payment(amount=service.price, user_id=user.id, service_id=service_id,
                                             payment_id=link['payment_id'])
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("💳 Перейти к оплате", url=link['payment_link']))
        await bot.send_message(chat_id=user_id,
                               text=f"💳 Оплата консультации «{service.name}»\n\nСумма: {service.price} ₽",
                               reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка оплаты: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("donat_pay_"))
async def donat_pay(call: CallbackQuery):
    service_id = int(call.data.split("_")[-1])
    user_id = call.from_user.id
    registration_data[user_id] = {"step": "donate_amount", "service_id": service_id}
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🔙 Назад", callback_data="book"))
    await bot.send_message(chat_id=user_id, text="💰 Введите сумму:\n\nНапример: 1500", reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_start")
async def back_to_start(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)
    await show_start_menu(user, call.message.chat.id, call.message.message_id)


# --- ПОДДЕРЖКА ---
@bot.callback_query_handler(func=lambda call: call.data == "support")
async def support_start(call: CallbackQuery):
    user_id = call.from_user.id
    if user_id not in registration_data: registration_data[user_id] = {}
    registration_data[user_id]["mode"] = "support"
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🔙 Назад", callback_data="back_to_start"))
    await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                text="🆘 Поддержка\n\nРасскажите, что у вас случилось.\n\nПросто отправьте сообщение в чат.",
                                reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data == "support_confirm")
async def support_confirm(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        if user_id not in registration_data or "support_message" not in registration_data[user_id]:
            await bot.answer_callback_query(call.id, text="❌ Сообщение не найдено", show_alert=True)
            return
        text = registration_data[user_id]["support_message"]
        user = await TelegramBotRepository.get_user(user_id)
        if not user:
            await bot.send_message(user_id, "❌ Вы не зарегистрированы. /start")
            return
        await SupportRepository.create(user_id=user.id, message=text)
        registration_data[user_id]["mode"] = None
        registration_data[user_id]["support_message"] = None
        await bot.send_message(chat_id=user_id, text="✅ Ваше обращение отправлено!")
        await notify_dev(f"🆕 Новое обращение в поддержку\n\n👤 Пользователь: {user.username}, ID {user.id}")
        await show_start_menu(user, call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Ошибка поддержки {user_id}: {e}")
        await bot.answer_callback_query(call.id, text="❌ Ошибка", show_alert=True)


# --- ТЕКСТОВЫЕ ХЕНДЛЕРЫ ---
@bot.message_handler(func=lambda message: message.from_user.id in create_service_data)
async def handle_create_service_text(message):
    user_id = message.from_user.id
    data = create_service_data[user_id]
    step = data.get("step", "type")

    if step == "name":
        data["name"] = message.text.strip()
        data["step"] = "desc"
        await bot.send_message(chat_id=user_id, text="📝 Введите описание (или «-», чтобы пропустить):")
    elif step == "desc":
        desc = message.text.strip()
        data["description"] = None if desc == "-" else desc
        data["step"] = "price"
        if data.get("is_donat"):
            data["price"] = 0
            await show_create_service_confirm(user_id)
        else:
            await bot.send_message(chat_id=user_id, text="💰 Введите цену консультации (Пример: 3000):")
    elif step == "price":
        try:
            price = float(message.text.strip())
            data["price"] = price
            await show_create_service_confirm(user_id)
        except ValueError:
            await bot.send_message(chat_id=user_id, text="❌ Неверный формат. Введите число:")


@bot.message_handler(
    func=lambda message: message.from_user.id in registration_data and registration_data[message.from_user.id].get(
        "step") == "donate_amount")
async def handle_donate_amount(message):
    user_id = message.from_user.id
    try:
        amount = float(message.text.strip())
        service_id = registration_data[user_id]["service_id"]
        service = await ServiceRepository.get_service_by_id(service_id)
        user = await TelegramBotRepository.get_user(user_id)

        link = await PaymentRepository.create_payment_link(amount=amount, desc=f"Оплата консультации: {service.name}",
                                                           user_id=user_id, service_id=service_id)
        await PaymentRepository.save_payment(amount=amount, user_id=user.id, service_id=service_id,
                                             payment_id=link['payment_id'])

        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("💳 Перейти к оплате", url=link['payment_link']))
        await bot.send_message(user_id, f"💳 Оплата консультации «{service.name}»\n\nСумма: {amount} ₽", reply_markup=kb)
        registration_data[user_id]["step"] = None
    except ValueError:
        await bot.send_message(user_id, "❌ Неверный формат. Введите число:")


@bot.message_handler(func=lambda message: True)
async def handle_text(message):
    user_id = message.from_user.id

    # Поддержка
    if user_id in registration_data and registration_data[user_id].get("mode") == "support":
        text = message.text
        if not text:
            await bot.send_message(user_id, "❌ Сообщение не может быть пустым.")
            return
        registration_data[user_id]["support_message"] = text
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("✅ Да, отправить", callback_data="support_confirm"),
               InlineKeyboardButton("❌ Отменить", callback_data="support_cancel"))
        await bot.send_message(chat_id=user_id, text=f"📝 Ваше сообщение:\n\n{text}\n\nВсё верно?", reply_markup=kb)
        return

    if user_id in create_service_data: return
    if user_id in registration_data and registration_data[user_id].get("step") == "donate_amount": return
    if user_id not in registration_data: return

    step = registration_data[user_id]["step"]

    # Шаг 1: Имя
    if step == "name":
        name = message.text.strip()
        if not Validation.validate_name(name):
            await bot.send_message(chat_id=user_id, text="❌ Имя должно быть на латинице, без пробелов. Пример: Ivan")
            return
        registration_data[user_id]["name"] = message.text
        registration_data[user_id]["step"] = "birth"
        await bot.send_message(chat_id=user_id,
                               text="📅 Теперь дату рождения, в формате ДД.ММ.ГГГГ (Пример: 31.01.2000):")

    # Шаг 2: Дата рождения
    elif step == "birth":
        birth = message.text.strip()
        if not Validation.validate_date(birth):
            await bot.send_message(chat_id=user_id,
                                   text="❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (Пример: 31.01.2000):")
            return
        registration_data[user_id]["birth"] = message.text
        registration_data[user_id]["step"] = "phone_wait"

        # ✅ ПОКАЗЫВАЕМ КНОПКУ ЗАПРОСА КОНТАКТА
        kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add(KeyboardButton(text="📱 Поделиться номером", request_contact=True))
        await bot.send_message(
            chat_id=user_id,
            text="📱 Отлично! Теперь поделись своим номером, нажав на кнопку ниже:",
            reply_markup=kb
        )

    # Шаг 3 (Текст не должен сюда попадать, но на всякий случай)
    elif step == "phone_wait":
        await bot.send_message(chat_id=user_id,
                               text="❌ Пожалуйста, нажмите на кнопку «Поделиться номером», чтобы продолжить.")


# ✅ ХЕНДЛЕР ДЛЯ ПРИЕМА КОНТАКТА
@bot.message_handler(content_types=['contact'])
async def handle_contact(message):
    user_id = message.from_user.id

    # Проверяем, что мы действительно ждем телефон при регистрации
    if user_id not in registration_data or registration_data[user_id].get("step") != "phone_wait":
        return

    try:
        phone = message.contact.phone_number
        registration_data[user_id]["phone"] = phone
        registration_data[user_id]["step"] = "confirm"

        data = registration_data[user_id]
        text = f"""
📋 Проверьте данные:
Имя: {data['name']}
Дата рождения: {data['birth']}
Телефон: {phone}

Всё верно?
        """
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Да", callback_data="confirm"),
               InlineKeyboardButton("❌ Нет", callback_data="cancel"))

        await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)

    except Exception as e:
        logger.error(f"Ошибка при получении контакта {user_id}: {e}")
        await bot.send_message(chat_id=user_id, text="❌ Ошибка при обработке номера.")


# --- АДМИНСКИЕ ГОЛОСОВЫЕ ---
@bot.message_handler(content_types=['voice'])
async def handle_admin_voice_send(message):
    user_id = message.from_user.id
    if not await AdminRepository.is_admin(user_id):
        await bot.send_message(user_id, "❌ Доступ ограничен")
        return
    if user_id not in admin_voice_data:
        await bot.send_message(user_id, "❌ Сначала выберите клиента в админке.")
        return

    consultation_id = admin_voice_data[user_id]["consultation_id"]
    consultation = await ConsultationRepository.get_by_id_with_user(consultation_id)
    if not consultation:
        await bot.send_message(user_id, "❌ Клиент не найден")
        return

    file_info = await bot.get_file(message.voice.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)

    await bot.send_voice(chat_id=consultation.user.telegram_id, voice=downloaded_file,
                         caption="🎤 Ваша бесплатная консультация.")
    await ConsultationRepository.mark_as_viewed(consultation_id)
    del admin_voice_data[user_id]
    await asyncio.sleep(0.5)

    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("📋 Посмотреть другие консультации", callback_data="book"))
    await bot.send_message(chat_id=consultation.user.telegram_id,
                           text="✨ Также вы можете посмотреть другие доступные консультации:", reply_markup=kb)
    await bot.send_message(user_id, "✅ Голосовое отправлено клиенту!")
    await bot.send_message(chat_id=user_id, text="🔐 Админ-панель\n\nВыберите действие ниже 👇",
                           reply_markup=get_admins_keyboard())


# connections
async def handle_webhook(request):
    try:
        body = await request.json()
        logger.info(f"Webhook received: {body}")
        update = telebot.types.Update.de_json(body)
        try:
            await bot.process_new_updates([update])
        except Exception as e:
            logger.error(f"process_new_updates error: {e}", exc_info=True)
        return web.Response(status=200, text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return web.Response(status=200, text="OK")


app.router.add_post(WEBHOOK_PATH, handle_webhook)


async def main():
    await bot.delete_webhook()
    await bot.set_webhook(url=WEBHOOK_URL)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='127.0.0.1', port=8080)
    await site.start()
    logger.info("Бот запущен")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())