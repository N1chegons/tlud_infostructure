import asyncio
import telebot
from aiohttp import web

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telebot.async_telebot import AsyncTeleBot

from src.config import settings
from src.logger_config import setup_logger
from src.telegram_bot.meneger_sending import notify_admins
from src.telegram_bot.models import User
from src.telegram_bot.repository import TelegramBotRepository, ConsultationRepository, Validation, AdminRepository, \
    ServiceRepository

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
    return kb

async def show_start_menu(user: User, chat_id: int, message_id: int = None):
    keyboard = InlineKeyboardMarkup()

    keyboard.row(InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    keyboard.row(InlineKeyboardButton(text="📋 Мои консультации", callback_data="my_consultations"))
    keyboard.row(InlineKeyboardButton(text="✍️ Записаться", callback_data="book"))


    await bot.edit_message_text(
        text=f"Привет {user.username}!\nТы уже зарегестрирован, выбери действие ниже 👇",
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=keyboard
    )
    return

# start
@bot.message_handler(commands=['start'])
async def start(message):
    user_id = message.from_user.id
    user = await TelegramBotRepository.get_user(user_id)
    logger.info(f"Пользователь {user_id} запустил бота")

    kb = InlineKeyboardMarkup()

    if not user:
        logger.info(f"Пользователь не зарегистрирован. Начало регистрации")
        kb.add(InlineKeyboardButton(text="Записаться на бесплатную консультацию", callback_data="register"))

        await bot.send_message(
            chat_id=message.chat.id,
            text="Привет! 🙌\n"
                 "Я цифровой психолог. Моя задача — показать, что твоя дата рождения — это не просто цифры в паспорте. "
                 "Это твой личный код, подпись Вселенной и ключ к счастливой жизни.\n\n"
                 "Готов узнать, что в тебе зашифровано? 👇",
            reply_markup=kb
        )
        return

    if user.has_free_consultation:
        logger.info(f"Пользователь зарегистрирован. Запись уже была произведена")

        keyboard = InlineKeyboardMarkup()

        keyboard.row(InlineKeyboardButton(text="👤 Профиль",  callback_data="profile"))
        keyboard.row(InlineKeyboardButton(text="📋 Мои консультации",  callback_data="my_consultations"))
        keyboard.row(InlineKeyboardButton(text="✍️ Записаться",  callback_data="book"))

        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Привет {user.username}!\nТы уже зарегестрирован, выбери действие ниже 👇",
            reply_markup=keyboard
        )
        return

    logger.info(f"Пользователь зарегистрирован. Запись на бесплатную консультацию")
    kb.add(InlineKeyboardButton(text="Записаться на бесплатную консультацию", callback_data="submit_request"))

    await bot.send_message(
        chat_id=message.chat.id,
        text="Привет! 🙌\n"
             "Я Людмила - цифровой психолог. Моя задача — показать, что твоя дата рождения — это не просто цифры в паспорте. "
             "Это твой личный код, подпись Вселенной и ключ к счастливой жизни.\n\n"
             "Готов узнать, что в тебе зашифровано? 👇",
        reply_markup=kb
    )

@bot.message_handler(commands=['admin'])
async def admin(message):
    user_id = message.from_user.id

    if not await AdminRepository.is_admin(user_id):
        await bot.send_message(
            chat_id=message.chat.id,
            text="❌ Доступ ограничен",
        )
    else:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🔐 **Админ-панель**\n\n"
                "Добро пожаловать в панель управления ботом!\n"
                "Здесь вы можете управлять записями на консультацию\n\n"
                "📌 **Доступные действия:**\n"
                "• 📋 Просмотр всех записей\n"
                "• ⚙️ Управление консультациями\n\n"
                "Выберите действие ниже 👇"
            ),
            reply_markup=get_admins_keyboard()
        )

# admin logic
create_service_data = {}
edit_service_data = {}

async def show_create_service_confirm(user_id: int):
    data = create_service_data[user_id]

    text = f"""
📋 Проверьте данные новой консультации:

📌 Название: {data['name']}
📝 Описание: {data.get('description', '—')}
💰 Цена: {data['price']} ₽

Всё верно?
    """

    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Да", callback_data="confirm_create_service"),
        InlineKeyboardButton("❌ Нет", callback_data="admin_paid_consultations_settings")
    )

    await bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=kb
    )

async def show_edit_service_confirm(user_id: int):
    data = edit_service_data[user_id]

    text = f"""
📋 Проверьте новые данные консультации:

📌 Название: {data['name']}
💰 Цена: {data['price']} ₽

Всё верно?
    """

    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Да", callback_data="confirm_edit_service"),
        InlineKeyboardButton("❌ Нет", callback_data="admin_paid_consultations_settings")
    )

    await bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_view_consultations")
async def admin_view_consultations(call: CallbackQuery):
    user_id = call.from_user.id

    try:
        logger.info(f"Администратор ID {user_id} просматривает список заявок на бесплатную консультацию")
        consultations = await ConsultationRepository.get_consultation_list()

        if not consultations:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=call.message.message_id,
                text="📭 Записей пока нет.",
            )
            return

        text = "📋 **Записи на консультацию:**\n\n"
        for idx, row in enumerate(consultations, 1):
            viewed_emoji = "🆕" if not row.is_viewed else "✅"
            text += (
                f"{viewed_emoji} {idx}. {row.username}\n"
                f"   📱 {row.phone_number}\n"
                f"   📅 {row.date_of_birth}\n\n"
            )
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("✅ Отметить просмотренные", callback_data="admin_mark_viewed"))
        kb.row( InlineKeyboardButton("🔙 Назад", callback_data="admin_back"))


        await bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная ошибка при просмотре у администратора ADMIN_ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == "admin_mark_viewed")
async def admin_mark_viewed(call: CallbackQuery):
    user_id = call.from_user.id

    try:
        logger.info(f"Администратор ID {user_id} отмечает просмотренную заявку")
        unviewed = await ConsultationRepository.get_unviewed_consultation_list()

        if not unviewed:
            await bot.answer_callback_query(call.id, "✅ Все записи уже просмотрены!")
            await admin_view_consultations(call)
            return

        text = "🆕 **Непросмотренные записи:**\n\n"
        for idx, row in enumerate(unviewed, 1):
            text += (
                f"{idx}. {row.username}\n"
                f"   📱 {row.phone_number}\n"
                f"   📅 {row.date_of_birth}\n\n"
            )

        text += "\nВыберите номер записи, чтобы отметить её как просмотренную:"

        kb = InlineKeyboardMarkup()
        row = []
        for idx, row_data in enumerate(unviewed, 1):
            row.append(InlineKeyboardButton(str(idx), callback_data=f"admin_mark_{row_data.consultation_id}"))  # 👈 ИСПРАВИЛ
            if len(row) == 5:
                kb.row(*row)
                row = []
        if row:
            kb.row(*row)

        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_view_consultations"))

        await bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная ошибка при помечании у администратора ADMIN_ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_mark_"))
async def admin_mark_single(call: CallbackQuery):
    user_id = call.from_user.id
    consultation_id = int(call.data.split("_")[-1])

    try:
        await ConsultationRepository.mark_as_viewed(consultation_id)

        await bot.answer_callback_query(call.id, "✅ Запись отмечена как просмотренная!")

        await admin_mark_viewed(call)

    except Exception as e:
        logger.error(f"Произошла неизвестная ошибка при помечани одной записи у администратора ADMIN_ID {user_id}, ошибка: {str(e)}")
        await bot.send_message(
            chat_id=call.message.chat.id,
            text="❌ Произошла неизвестная ошибка",
        )

@bot.callback_query_handler(func=lambda call: call.data == "admin_paid_consultations_settings")
async def admin_paid_consultations_settings(call: CallbackQuery):
    user_id = call.from_user.id

    if user_id in create_service_data:
        del create_service_data[user_id]

    try:
        kb = InlineKeyboardMarkup()

        paid_consultations = await ServiceRepository.get_services_list_by_admin()

        if not paid_consultations:
            text = "😕 Платных консультаций пока нет.\n\nВы можете ее добавить, нажмите на ➕ Добавить"
        else:
            text = "📋 Список консультаций:\n\n"
            for idx, con in enumerate(paid_consultations, 1):
                text += (f"{idx}. {con.name} — {con.price} ₽\n"
                         f"{con.description}\n\n")

        # if not paid_consultations:
        #     text = "😕 Платных консультаций пока нет.\n\nВы можете ее добавить, нажмите на - ➕ Добавить"
        # else:
        #     text = "⚒ Выберите консультацию для редактирования:\n\n"
        #
        #     for con in paid_consultations:
        #         kb.row(
        #             InlineKeyboardButton(
        #                 f"💬 {con.name}",
        #                 callback_data=f"admin_service_{con.id}"
        #             )
        #         )

        kb.add(
            InlineKeyboardButton("➕ Добавить", callback_data="create_service"),
            InlineKeyboardButton("🔙 Назад", callback_data="admin_back"),
            InlineKeyboardButton("🗑️ Удалить", callback_data="admin_delete_service")
        )

        await bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=kb
        )

    except Exception as e:
        if "Error code: 400" in str(e):
            pass

        logger.error(
            f"Произошла неизвестная ошибка при просмотре у администратора ADMIN_ID {user_id}, ошибка: {str(e)}")
        await bot.send_message(
            chat_id=call.message.chat.id,
            text="❌ Произошла неизвестная ошибка",
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("create_service"))
async def create_service(call: CallbackQuery):
    user_id = call.from_user.id

    try:
        create_service_data[user_id] = {}

        await bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="✏️ Введите название консультации:"
        )

    except Exception as e:
        logger.error(
            f"Произошла неизвестная ошибка при создании у администратора ADMIN_ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

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

    text += "\nВыберите номер конусльтации, чтобы удалить её:"

    kb = InlineKeyboardMarkup()
    row = []
    for idx, service in enumerate(services, 1):
        row.append(InlineKeyboardButton(str(idx), callback_data=f"admin_delete_service_{service.id}"))
        if len(row) == 5:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)

    kb.row(InlineKeyboardButton("🔙 Назад", callback_data="admin_paid_consultations_settings"))

    await bot.edit_message_text(
        chat_id=user_id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=kb
    )

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
            await bot.send_message(chat_id=user_id, text="❌ Данные не найдены. Начните заново.")
            return

        await ServiceRepository.create_service(
            name=data["name"],
            price=data["price"],
            description=data["description"]
        )

        del create_service_data[user_id]

        await bot.answer_callback_query(call.id, text="✅ Консультация создана!")

        await admin_paid_consultations_settings(call)

        logger.info(f"Администратор TG_ID {user_id} успешно создал новую консультацию")

    except Exception as e:
        logger.error(f"Ошибка при создании: {e}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == "admin_back")
async def admin_back(call: CallbackQuery):
    user_id = call.from_user.id

    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=(
            "🔐 **Админ-панель**\n\n"
            "Добро пожаловать в панель управления ботом!\n"
            "Здесь вы можете управлять записями на консультацию\n\n"
            "📌 **Доступные действия:**\n"
            "• 📋 Просмотр всех записей\n"
            "• ⚙️ Управление консультациями\n\n"
            "Выберите действие ниже 👇"
        ),
        reply_markup=get_admins_keyboard()
    )

# logic buttons
registration_data = {}

# -- free consult and register logic
@bot.callback_query_handler(func=lambda call: call.data == "submit_request")
async def recording_consultation(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)

    try:
        logger.info(f"Пользователь TG_ID {user_id} записывается на консультацию")

        if not user:
            logger.warning(f"Пользователь не зарегестрирован")
            await bot.edit_message_text(
                text=f"❌ Видимо вы не зарегестрированы, отправить в чат для регистрации - /start",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
            return


        await ConsultationRepository.create_consultation(user.id, "Бесплатная консультация")
        await TelegramBotRepository.update_free_consultation_status(user_id)

        await notify_admins(f"Новая запись на консультацию. Клиент: {user.username}.\n\nПерейти к записям 👇")

        await bot.edit_message_text(
            text=f"✅ {user.username}, вы успешно записались на консультацию! Ожидайте ответа...",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная ошибка при записи у пользователя ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == "register")
async def register(call: CallbackQuery):
    user_id = call.from_user.id

    registration_data[user_id] = {"step": "name"}

    await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Ты еще не зарегестрирован, давай пройдем небольшую регистрацию!")
    await bot.send_message(chat_id=call.message.chat.id, text="✏️ Для начала, как тебя зовут?\n (Введите имя используя латиницу, пример: Ivan)")

@bot.callback_query_handler(func=lambda call: call.data == "confirm")
async def confirm(call: CallbackQuery):
    user_id = call.from_user.id
    data = registration_data.get(user_id)

    if not data:
        logger.warning(f"Пользователь не зарегестрирован")
        await bot.edit_message_text(
            text=f"❌ Видимо вы не зарегестрированы, отправьте в чат для регистрации - /start",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )

    try:
        logger.info(f"Регистрация для пользователя TG_ID {user_id}")

        user = await TelegramBotRepository.register_user(user_id, data["name"], data["birth"], data["phone"])
        user = await TelegramBotRepository.get_user(user_id)

        await ConsultationRepository.create_consultation(user.id, "Бесплатная консультация")
        await TelegramBotRepository.update_free_consultation_status(user_id)

        await notify_admins(f"Новая запись на консультацию. Клиент: {user.username}.\n\nПерейти к записям 👇")

        del registration_data[user_id]


        await bot.edit_message_text(
            text=f"✅ {user.username}, вы успешно записались на консультацию! Ожидайте ответа...",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная оишбка при регистрации у пользователя ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
async def cancel(call: CallbackQuery):
    user_id = call.from_user.id

    if user_id in registration_data:
        del registration_data[user_id]

    registration_data[user_id] = {"step": "name"}

    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🔄 Давай попробуем ещё раз! Как тебя зовут?"
    )

# -- base logic
@bot.callback_query_handler(func=lambda call: call.data == "profile")
async def view_profile(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)

    try:
        logger.info(f"Получение профиля пользователя TG_ID {user_id}")
        kb = InlineKeyboardMarkup()

        if not user:
            logger.warning(f"Пользователь не зарегестрирован")
            await bot.edit_message_text(
                text=f"❌ Видимо вы не зарегестрированы, отправить в чат для регистрации - /start",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
            return

        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_start"))

        await bot.edit_message_text(
            text=(
                f"👤 Мой профиль\n\n"
                f"🪪 Имя: {user.username}\n"
                f"📱 Телефон: {user.phone_number}\n"
                f"📅 Дата рождения: {user.date_of_birth}"
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная ошибка при получении профиля у пользователя ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == "my_consultations")
async def view_my_consultation(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)

    try:
        logger.info(f"Получение записей пользователя TG_ID {user_id}")
        kb = InlineKeyboardMarkup()

        if not user:
            logger.warning(f"Пользователь не зарегестрирован")
            await bot.edit_message_text(
                text=f"❌ Видимо вы не зарегестрированы, отправить в чат для регистрации - /start",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
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

                text += (
                    f"{idx}. {row.service_name}\n"
                    f"📌 Статус записи: {viewed_emoji} \n"
                    f"📅 Дата записи: {created_date}\n\n"
                )

        await bot.edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная ошибка при получение записей у пользователя ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == "book")
async def view_paid_consultation(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)

    try:
        logger.info(f"Получение платных консультаций, пользователь TG_ID {user_id}")

        kb = InlineKeyboardMarkup()
        paid_consultations = await ServiceRepository.get_services_list()

        if not paid_consultations:
            text = "😕 Платных консультаций пока нет."

        else:
            text = "💳 Выберите консультацию:\n\n"

            for con in paid_consultations:
                kb.row(
                    InlineKeyboardButton(
                        f"💬 {con.name}",
                        callback_data=f"consult_{con.id}"
                    )
                )

        kb.row(InlineKeyboardButton("🔙 Назад", callback_data="back_to_start"))

        await bot.edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная оишбка при просмотре консультаций ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("consult_"))
async def service_card(call: CallbackQuery):
    service_id = int(call.data.split("_")[1])
    user_id = call.from_user.id

    try:
        logger.info(f"Пользовтель TG_ID {user_id} просматривает платную консультацию с ID {service_id}")
        service = await ServiceRepository.get_service_by_id(service_id)

        text = f"""
📌 {service.name}

📝 Описание: {service.description or '—'}

💰 Цена: {service.price} ₽

Нажмите «Оплатить», чтобы перейти к оплате.
        """

        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton(f"💳 Оплатить {service.price} ₽", callback_data="foo"))
        kb.row(InlineKeyboardButton("🔙 Назад", callback_data="book"))

        await bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная ошибка при просмотре консультации с SERV_ID {service_id}, TG_ID {user_id}, ошибка: {str(e)}")
        await bot.answer_callback_query(
            call.id,
            text="❌ Произошла ошибка",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_start")
async def back_to_start(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)

    await show_start_menu(user, call.message.chat.id, call.message.message_id)

# logic text
@bot.message_handler(func=lambda message: message.from_user.id in create_service_data)
async def handle_create_service_text(message):
    user_id = message.from_user.id
    data = create_service_data[user_id]

    step = data.get("step", "name")

    if step == "name":
        data["name"] = message.text.strip()
        data["step"] = "desc"
        await bot.send_message(
            chat_id=user_id,
            text="📝 Введите описание консультации (или отправьте «-», чтобы пропустить):"
        )

    elif step == "desc":
        desc = message.text.strip()
        data["description"] = None if desc == "-" else desc
        data["step"] = "price"
        await bot.send_message(
            chat_id=user_id,
            text="💰 Введите цену услуги (в рублях. Пример: 3000):"
        )

    elif step == "price":
        try:
            price = float(message.text.strip())
            data["price"] = price
            await show_create_service_confirm(user_id)

        except ValueError:
            await bot.send_message(
                chat_id=user_id,
                text="❌ Неверный формат. Введите число, например: 3000"
            )

@bot.message_handler(func=lambda message: message.from_user.id in edit_service_data)
async def handle_edit_service_text(message):
    user_id = message.from_user.id
    data = edit_service_data[user_id]

    step = data.get("step", "name")

    if step == "name":
        data["name"] = message.text.strip()
        data["step"] = "price"

        await bot.send_message(
            chat_id=user_id,
            text=f"💰 Введите новую цену консультации:\n\n(текущая: {data['price']} ₽)"
        )

    elif step == "price":
        try:
            price = float(message.text.strip())
            data["price"] = price
            data["step"] = "confirm"

            await show_edit_service_confirm(user_id)

        except ValueError:
            await bot.send_message(
                chat_id=user_id,
                text="❌ Неверный формат. Введите число, например: 3000"
            )

@bot.message_handler(func=lambda message: True)
async def handle_text(message):
    user_id = message.from_user.id

    if user_id not in registration_data:
        return

    step = registration_data[user_id]["step"]

    if step == "name":
        name = message.text.strip()
        if not Validation.validate_name(name):
            await bot.send_message(chat_id=user_id,
                                   text="❌ Имя должно быть на латинице, без пробелов. Пример: Ivan")
            return

        registration_data[user_id]["name"] = message.text
        registration_data[user_id]["step"] = "birth"
        await bot.send_message(chat_id=user_id, text="📅 Теперь дату рождения, в формате ДД.ММ.ГГГГ (Пример: 31.01.2000):")

    elif step == "birth":
        birth = message.text.strip()

        if not Validation.validate_date(birth):
            await bot.send_message(
                chat_id=user_id,
                text="❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (Пример: 31.01.2000):"
            )
            return

        registration_data[user_id]["birth"] = message.text
        registration_data[user_id]["step"] = "phone_wait"

        await bot.send_message(
            chat_id=user_id,
            text="📱 Поделись своим номером, чтобы с тобой можно было связаться \n(формат: +79001234567):"
        )

    elif step == "phone_wait":
        phone = message.text.strip()

        if not Validation.validate_phone(phone):
            await bot.send_message(
                user_id,
                "❌ Неверный формат. Введите номер в формате +7XXXXXXXXXX \n(например, +79001234567):"
            )
            return

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
        kb.add(
            InlineKeyboardButton("✅ Да", callback_data="confirm"),
            InlineKeyboardButton("❌ Нет", callback_data="cancel")
        )

        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=kb
        )

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