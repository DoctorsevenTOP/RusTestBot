"""Telegram бот для проверки знаний по русскому языку"""
import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import data_manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Логирование информации о сервере
logger.info("=" * 50)
logger.info("ЗАПУСК БОТА")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Script location: {os.path.dirname(os.path.abspath(__file__))}")
logger.info(f"Data directory: {data_manager.DATA_DIR}")
logger.info(f"Database file: {data_manager.DB_FILE}")
logger.info(f"Database exists: {os.path.exists(data_manager.DB_FILE)}")

# Проверяем права на запись
try:
    test_file = os.path.join(data_manager.DATA_DIR, ".write_test")
    with open(test_file, "w") as f:
        f.write("test")
    os.remove(test_file)
    logger.info("✅ Права на запись в data/: OK")
except Exception as e:
    logger.error(f"❌ НЕТ ПРАВ НА ЗАПИСЬ в {data_manager.DATA_DIR}: {e}")

# Проверяем базу данных
try:
    conn = sqlite3.connect(data_manager.DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE admin = 1")
    admin_count = cursor.fetchone()[0]
    conn.close()
    logger.info(f"✅ База данных: OK (пользователей: {user_count}, администраторов: {admin_count})")
except Exception as e:
    logger.error(f"❌ ОШИБКА БАЗЫ ДАННЫХ: {e}")

logger.info("=" * 50)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Хранилище для данных Mini App
mini_app_results = {}


# === Состояния для FSM ===
class WaitForName(StatesGroup):
    waiting_for_name = State()


class CreateTest(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_questions = State()
    waiting_for_question_text = State()
    waiting_for_answer = State()
    adding_more_questions = State()


class TakeTest(StatesGroup):
    in_progress = State()
    answering = State()


class BecomeAdmin(StatesGroup):
    waiting_for_code = State()


# === Вспомогательные функции ===
def get_main_keyboard(is_admin_user: bool) -> ReplyKeyboardMarkup:
    """Получить главное меню"""
    buttons = [
        [KeyboardButton(text="📋 Список тестов")],
        [KeyboardButton(text="🏆 Таблица лидеров")],
        [KeyboardButton(text="📊 Мои результаты")],
    ]
    if is_admin_user:
        buttons.append([KeyboardButton(text="➕ Создать тест")])
        buttons.append([KeyboardButton(text="👥 Администраторы")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# === Команда /start ===
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user = data_manager.get_user(user_id)

    if user:
        # Пользователь уже зарегистрирован
        await message.answer(
            f"Привет, <b>{user['name']}</b>!\n"
            f"Твой Telegram ID: <code>{user_id}</code>\n\n"
            f"Выбери действие в меню:",
            reply_markup=get_main_keyboard(data_manager.is_admin(user_id))
        )
    else:
        # Запрашиваем имя
        await message.answer(
            f"Привет! Твой Telegram ID: <code>{user_id}</code>\n\n"
            f"Для начала работы представься. Напиши своё имя:\n\n"
            f"Используй /help для просмотра всех команд"
        )
        await state.set_state(WaitForName.waiting_for_name)


# === Команда /help ===
@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показать справку по командам"""
    user_id = message.from_user.id
    is_admin_user = data_manager.is_admin(user_id)

    text = "<b>📚 Справка по командам бота</b>\n\n"

    text += "<b>👤 Для всех пользователей:</b>\n"
    text += "/start - Начать работу, узнать свой ID\n"
    text += "/help - Эта справка\n"
    text += "/ping - Проверка работоспособности\n"
    text += "/me - Мой профиль и статус\n"
    text += "/admin - Стать администратором (код: 6418237)\n"
    text += "/insert - Задания на вставку букв (Mini App)\n"
    text += "📋 Список тестов - Пройти тест\n"
    text += "🏆 Таблица лидеров - Лучшие результаты\n"
    text += "📊 Мои результаты - История прохождений\n\n"

    if is_admin_user:
        text += "<b>🔧 Для администраторов:</b>\n"
        text += "➕ Создать тест - Интерактивное создание\n"
        text += "/edit_test - Редактор тестов (Mini App)\n"
        text += "/export_test <ID> - Экспорт теста в JSON\n"
        text += "/load_test - Загрузка теста из JSON\n"
        text += "/toggle_test - Вкл/выкл тесты\n"
        text += "/delete_test - Удалить тест\n"
        text += "/admins - Список администраторов\n"
        text += "/cancel - Отмена действия\n\n"

    text += "<b>ℹ️ Дополнительно:</b>\n"
    text += "• Тесты выбираются кнопками из списка\n"
    text += "• Вопросы бывают с одиночным и множественным выбором\n"
    text += "• В таблице лидеров показан лучший результат\n"
    text += "• Имена пользователей должны быть уникальны\n\n"

    text += "<i>Бот: Русский язык - Тесты и проверка знаний</i>"

    await message.answer(text, parse_mode="HTML")


# === Команда /ping ===
@router.message(Command("ping"))
async def cmd_ping(message: Message):
    """Проверка работоспособности бота"""
    import platform
    
    text = "🏓 <b>Pong!</b>\n\n"
    text += f"✅ Бот работает\n"
    text += f"🖥️ Сервер: {platform.system()} {platform.release()}\n"
    text += f"📁 Директория данных: <code>{data_manager.DATA_DIR}</code>\n"
    text += f"👤 Ваш ID: <code>{message.from_user.id}</code>\n"
    
    # Проверяем права на запись
    try:
        test_file = os.path.join(data_manager.DATA_DIR, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        text += "\n✅ Права на запись: OK"
    except Exception as e:
        text += f"\n❌ Права на запись: ERROR - {e}"
    
    await message.answer(text, parse_mode="HTML")


# === Команда /me ===
@router.message(Command("me"))
async def cmd_me(message: Message):
    """Показать информацию о пользователе"""
    user_id = message.from_user.id
    user = data_manager.get_user(user_id)

    if user:
        text = f"<b>👤 Ваш профиль:</b>\n\n"
        text += f"Имя: <b>{user.get('name', 'N/A')}</b>\n"
        text += f"ID: <code>{user_id}</code>\n"
        text += f"Администратор: {'✅ Да' if user.get('admin') else '❌ Нет'}\n"
        
        reg_date = user.get('registered_at', 'N/A')
        if reg_date != 'N/A':
            reg_date = data_manager.format_date_msk(reg_date)
        text += f"Зарегистрирован: <code>{reg_date}</code>\n"

        if user.get('admin'):
            admin_date = user.get('admin_updated_at', 'N/A')
            if admin_date != 'N/A':
                admin_date = data_manager.format_date_msk(admin_date)
            text += f"Админ с: <code>{admin_date}</code>\n"
    else:
        text = "❌ Вы ещё не зарегистрированы.\nНажмите /start для начала работы."

    await message.answer(text, parse_mode="HTML")


# === Mini App - Задания на вставку букв ===
@router.message(Command("insert"))
async def cmd_insert_app(message: Message):
    """Запустить Mini App с заданием на вставку букв"""
    user = data_manager.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    # Получаем тесты с вопросами типа insert_letter
    tests = data_manager.get_tests(only_active=True)
    
    insert_tests = []
    for test_id, test in tests.items():
        for q in test.get("questions", []):
            if q.get("type") == "insert_letter":
                insert_tests.append({
                    "test_id": test_id,
                    "title": test["title"],
                    "question": q
                })
    
    if not insert_tests:
        await message.answer(
            "❌ Пока нет доступных заданий на вставку букв.\n\n"
            "Администраторы могут создать их через /load_test"
        )
        return
    
    # Создаём клавиатуру с доступными заданиями
    buttons = []
    for i, task in enumerate(insert_tests[:10]):  # Максимум 10
        buttons.append([InlineKeyboardButton(
            text=f"📝 {task['title']}",
            callback_data=f"insert_app_{task['test_id']}_{i}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "📱 <b>Выберите задание</b>\n\n"
        "Вам нужно будет вставлять пропущенные буквы в слова.\n"
        "Нажмите на пропуск, затем выберите правильную букву.",
        reply_markup=keyboard
    )


# === Редактор тестов (Mini App) ===
@router.message(Command("edit_test"))
async def cmd_edit_test(message: Message):
    """Запустить редактор тестов"""
    if not data_manager.is_admin(message.from_user.id):
        await message.answer("❌ Эта команда доступна только администраторам.")
        return
    
    # URL редактора (замените на ваш хостинг)
    editor_url = "https://doctorseventop.github.io/RusTestBot/editor"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Открыть редактор", web_app={"url": editor_url})]
    ])
    
    await message.answer(
        "🛠️ <b>Редактор тестов</b>\n\n"
        "Выберите тест из списка или создайте новый.\n"
        "Добавляйте вопросы разных типов и отправляйте в бота.",
        reply_markup=keyboard
    )


# === Экспорт теста в JSON ===
@router.message(Command("export_test"))
async def cmd_export_test(message: Message):
    """Экспортировать тест в JSON"""
    if not data_manager.is_admin(message.from_user.id):
        await message.answer("❌ Эта команда доступна только администраторам.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Использование: <code>/export_test &lt;ID&gt;</code>\n\n"
            "Пример: <code>/export_test 1</code>"
        )
        return
    
    test_id = args[1].strip()
    test = data_manager.get_test(test_id)
    
    if not test:
        await message.answer(f"❌ Тест с ID <code>{test_id}</code> не найден")
        return
    
    # Формируем JSON
    import json
    export_data = {
        "title": test["title"],
        "description": test.get("description", ""),
        "active": test.get("active", True),
        "questions": test.get("questions", [])
    }
    
    json_text = json.dumps(export_data, ensure_ascii=False, indent=2)
    
    # Отправляем файлом
    from io import BytesIO
    json_bytes = BytesIO(json_text.encode('utf-8'))
    json_bytes.name = f"test_{test_id}.json"
    
    await message.answer_document(
        json_bytes,
        caption=f"📄 Тест: {test['title']}\nID: {test_id}"
    )


@router.message(F.web_app_data)
async def handle_editor_result(message: Message):
    """Обработка данных из редактора"""
    if not data_manager.is_admin(message.from_user.id):
        return
    
    try:
        import json
        data = json.loads(message.web_app_data.data)
        
        action = data.get("action")
        
        if action == "get_tests_list":
            # Отправляем список тестов
            tests = data_manager.get_tests()
            tests_list = [
                {
                    "test_id": tid,
                    "title": t["title"],
                    "active": t.get("active", True),
                    "questions": t.get("questions", [])
                }
                for tid, t in tests.items()
            ]
            
            # Отправляем список в редактор
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📚 Обновить список", callback_data="refresh_tests")]
            ])
            await message.answer(
                "📋 Список тестов отправлен в редактор",
                reply_markup=keyboard
            )
            # Для Mini App нужно использовать answer_web_app_query
            # Это упрощённая версия
            
        elif action == "create_test":
            # Создаём новый тест
            test_id = data_manager.generate_test_id()
            test_data = {
                "title": data["title"],
                "description": data.get("description", ""),
                "active": data.get("active", True),
                "questions": data["questions"],
                "created_by": message.from_user.id,
                "created_at": data_manager.get_now_msk()
            }
            
            data_manager.save_test(test_id, test_data)
            
            await message.answer(
                f"✅ <b>Тест создан!</b>\n\n"
                f"ID: <code>{test_id}</code>\n"
                f"Название: {data['title']}\n"
                f"Вопросов: {len(data['questions'])}\n\n"
                f"Теперь пользователи могут проходить этот тест."
            )
            
        elif action == "update_test":
            # Обновляем существующий тест
            test_id = data.get("test_id")
            
            if not test_id:
                await message.answer("❌ Не указан ID теста")
                return
            
            test = data_manager.get_test(test_id)
            if not test:
                await message.answer(f"❌ Тест с ID <code>{test_id}</code> не найден")
                return
            
            test_data = {
                "title": data["title"],
                "description": data.get("description", ""),
                "active": test.get("active", True),
                "questions": data["questions"],
                "updated_by": message.from_user.id,
                "updated_at": data_manager.get_now_msk()
            }
            
            data_manager.save_test(test_id, test_data)
            
            await message.answer(
                f"✅ <b>Тест обновлён!</b>\n\n"
                f"ID: <code>{test_id}</code>\n"
                f"Название: {data['title']}\n"
                f"Вопросов: {len(data['questions'])}\n\n"
                f"Изменения применены."
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("insert_app_"))
async def launch_insert_app(callback: CallbackQuery):
    """Запуск Mini App с заданием"""
    parts = callback.data.replace("insert_app_", "").split("_")
    test_id = parts[0]
    question_idx = int(parts[1]) if len(parts) > 1 else 0
    
    test = data_manager.get_test(test_id)
    if not test:
        await callback.answer("Тест не найден", show_alert=True)
        return
    
    # Находим вопросы типа insert_letter
    insert_questions = [q for q in test.get("questions", []) if q.get("type") == "insert_letter"]
    
    if not insert_questions or question_idx >= len(insert_questions):
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    
    question = insert_questions[question_idx]
    
    # Формируем данные для Mini App
    app_data = {
        "test_id": test_id,
        "task_id": f"insert_{test_id}_{question_idx}",
        "title": test["title"],
        "description": question.get("description", "Вставьте пропущенные буквы"),
        "questions": [{
            "text": question["text"],
            "gaps": question["gaps"],
            "letters": question["letters"]
        }]
    }
    
    # Создаём URL для Mini App
    import json
    from urllib.parse import quote
    
    # В реальном проекте замените на ваш URL хостинга
    app_url = f"https://doctorseventop.github.io/RusTestBot/miniapp.html?data={quote(json.dumps(app_data))}"
    
    # Для локального тестирования можно использовать GitHub Pages или аналогичный хостинг
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить", web_app={"url": app_url})]
    ])
    
    await callback.message.answer(
        f"📝 <b>{test['title']}</b>\n\n"
        f"Нажмите кнопку ниже чтобы начать:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.message(F.web_app_data)
async def handle_miniapp_result(message: Message):
    """Обработка результатов из Mini App"""
    try:
        import json
        result = json.loads(message.web_app_data.data)
        
        user_id = message.from_user.id
        test_id = result.get("test_id")
        score = result.get("score", 0)
        total = result.get("total", 0)
        percentage = result.get("percentage", 0)
        
        # Сохраняем результат
        data_manager.save_result(user_id, test_id, score, total, [{
            "type": "insert_letter",
            "score": score,
            "total": total,
            "answers": result.get("answers", {})
        }])
        
        # Показываем результат
        emoji = "🏆" if percentage >= 80 else "👍" if percentage >= 60 else "📚"
        
        await message.answer(
            f"{emoji} <b>Результат сохранён!</b>\n\n"
            f"<b>{test_id}</b>\n"
            f"Правильно: {score} из {total}\n"
            f"Процент: {percentage}%\n\n"
            f"Результат добавлен в таблицу лидеров! 🏆"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки результата: {e}")


# === Команда /admin - стать администратором ===
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Начать процесс получения прав администратора"""
    user = data_manager.get_user(message.from_user.id)
    
    if user and user.get("admin"):
        await message.answer("✅ Вы уже являетесь администратором!")
        return
    
    await message.answer(
        "🔐 <b>Введите код администратора</b>\n\n"
        "Отправьте код для получения прав администратора:\n"
        "<i>(код можно узнать у разработчика)</i>\n\n"
        "Нажмите /cancel для отмены"
    )
    await state.set_state(BecomeAdmin.waiting_for_code)


@router.message(BecomeAdmin.waiting_for_code)
async def process_admin_code(message: Message, state: FSMContext):
    """Проверка кода администратора"""
    code = message.text.strip()
    
    # Правильный код
    if code == "6418237":
        # Назначаем администратором
        data_manager.set_admin_status(message.from_user.id, True)
        
        await state.clear()
        await message.answer(
            "✅ <b>Поздравляем!</b>\n\n"
            "Вы получили права администратора.\n\n"
            "Теперь вам доступны команды:\n"
            "➕ Создать тест\n"
            "/load_test - Загрузка теста из JSON\n"
            "/toggle_test - Вкл/выкл тесты\n"
            "/admins - Список администраторов\n\n"
            "Выберите действие в меню:",
            reply_markup=get_main_keyboard(True)
        )
    else:
        await message.answer(
            "❌ <b>Неверный код!</b>\n\n"
            "Пожалуйста, проверьте код и попробуйте снова.\n\n"
            "Нажмите /cancel для отмены или введите правильный код:"
        )


# === Команда /admins - список администраторов ===
@router.message(Command("admins"))
async def cmd_admins(message: Message):
    """Показать список всех администраторов"""
    user = data_manager.get_user(message.from_user.id)

    # Показываем только администраторам
    if not user or not user.get("admin"):
        await message.answer("❌ Эта команда доступна только администраторам.")
        return

    admins = data_manager.get_all_admins()

    if not admins:
        await message.answer("❌ Нет администраторов.")
        return

    text = "👥 <b>Список администраторов:</b>\n\n"
    for i, admin in enumerate(admins, 1):
        name = admin.get("name", "Неизвестный")
        user_id = admin.get("telegram_id", "?")
        admin_since = admin.get("admin_updated_at", "")
        if admin_since:
            admin_since = data_manager.format_date_msk(admin_since)

        text += f"{i}. <b>{name}</b>\n"
        text += f"   ID: <code>{user_id}</code>\n"
        if admin_since:
            text += f"   Админ с: {admin_since}\n\n"
        else:
            text += "\n"

    text += f"Всего администраторов: <b>{len(admins)}</b>"
    await message.answer(text)


@router.message(WaitForName.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Сохранение имени пользователя"""
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Пожалуйста, введите корректное имя:")
        return
    
    # Проверяем уникальность имени
    if data_manager.is_name_taken(name):
        existing_user = data_manager.get_user_by_name(name)
        if existing_user and existing_user.get("telegram_id") == message.from_user.id:
            # Это тот же пользователь, просто обновляем
            pass
        else:
            await message.answer(
                f"❌ Имя <b>{name}</b> уже занято другим пользователем!\n\n"
                f"Пожалуйста, выберите другое имя (можно добавить фамилию или цифры):"
            )
            return

    data_manager.save_user(message.from_user.id, name)
    await state.clear()

    await message.answer(
        f"Приятно познакомиться, <b>{name}</b>!\n"
        f"Теперь ты можешь проходить тесты по русскому языку.\n\n"
        f"Твой Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"Выбери действие в меню:",
        reply_markup=get_main_keyboard(data_manager.is_admin(message.from_user.id))
    )


# === Администраторы (кнопка) ===
@router.message(F.text == "👥 Администраторы")
async def show_admins_button(message: Message):
    """Показать список администраторов (кнопка)"""
    await cmd_admins(message)


# === Список тестов ===
@router.message(F.text == "📋 Список тестов")
async def show_tests(message: Message):
    """Показать список доступных тестов"""
    tests = data_manager.get_tests(only_active=True)

    if not tests:
        await message.answer("Пока нет доступных тестов.")
        return

    text = "<b>📚 Доступные тесты:</b>\n\n"
    buttons = []

    for test_id, test in tests.items():
        questions_count = len(test.get("questions", []))
        text += f"<b>{test_id}. {test['title']}</b>\n"
        text += f"{test.get('description', 'Без описания')}\n"
        text += f"Вопросов: {questions_count}\n\n"
        buttons.append([InlineKeyboardButton(text=f"▶️ {test['title']}", callback_data=f"start_test_{test_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("start_test_"))
async def begin_test(callback: CallbackQuery, state: FSMContext):
    """Начало прохождения теста"""
    test_id = callback.data.replace("start_test_", "")
    test = data_manager.get_test(test_id)

    if not test:
        await callback.answer("Тест не найден", show_alert=True)
        return
    
    # Проверяем активность теста
    if not test.get("active", True):
        await callback.answer("Этот тест временно недоступен", show_alert=True)
        return

    await state.update_data(
        current_test_id=test_id,
        current_question=0,
        score=0,
        answers=[]
    )
    await state.set_state(TakeTest.in_progress)

    question = test["questions"][0]
    await show_question(callback.message, question, 1, len(test["questions"]))
    await callback.answer()


async def show_question(message, question, question_num, total):
    """Показать вопрос с вариантами ответов или полем ввода"""
    q_type = question.get("type", "single")
    options = question.get("options")
    answer = question.get("answer")
    
    # Проверяем множественный выбор по типу или по структуре answer
    is_multiple = (q_type == "multiple" or 
                   isinstance(answer, list) or
                   (options is not None))
    
    if is_multiple and options:
        # Множественный выбор - создаём inline-кнопки
        buttons = []
        for i, option in enumerate(options):
            buttons.append([InlineKeyboardButton(text=option, callback_data=f"answer_option_{i}")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(
            f"<b>Вопрос {question_num} из {total}</b>\n\n"
            f"{question['text']}\n\n"
            f"<i>Выберите все правильные ответы (можно несколько):</i>\n"
            f"<i>Нажмите ✅ Готово, когда закончите</i>",
            reply_markup=keyboard
        )
        
        # Кнопка "Готово"
        done_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Готово", callback_data="answer_done")]
        ])
        await message.answer("<i>Отметьте все правильные варианты и нажмите Готово</i>", reply_markup=done_keyboard)
    else:
        # Одиночный ответ - текстовое поле
        await message.answer(
            f"<b>Вопрос {question_num} из {total}</b>\n\n"
            f"{question['text']}\n\n"
            f"<i>Введи свой ответ:</i>"
        )


@router.callback_query(F.data.startswith("answer_option_"))
async def handle_option_select(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора варианта ответа"""
    data = await state.get_data()
    selected = data.get("selected_options") or []  # Если None, создаём пустой список
    
    option_idx = int(callback.data.replace("answer_option_", ""))
    
    if option_idx in selected:
        selected.remove(option_idx)
    else:
        selected.append(option_idx)
    
    await state.update_data(selected_options=selected)
    
    # Обновляем кнопки, показывая выбранные галочками
    try:
        data = await state.get_data()
        test_id = data["current_test_id"]
        current_question = data["current_question"]
        test = data_manager.get_test(test_id)
        question = test["questions"][current_question]
        
        # Создаём кнопки с выделением выбранных
        buttons = []
        for i, option in enumerate(question["options"]):
            if i in selected:
                button_text = f"✅ {option}"
            else:
                button_text = option
            buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"answer_option_{i}")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except:
        pass  # Игнорируем если нельзя редактировать
    
    await callback.answer()


@router.callback_query(F.data == "answer_done")
async def handle_answer_done(callback: CallbackQuery, state: FSMContext):
    """Завершение ответа на вопрос с множественным выбором"""
    data = await state.get_data()
    selected = data.get("selected_options", [])
    
    if not selected:
        await callback.answer("Выберите хотя бы один вариант!", show_alert=True)
        return
    
    await process_multiple_answer(callback, state, selected)
    await callback.answer()


async def process_multiple_answer(callback: CallbackQuery, state: FSMContext, selected_indices: list):
    """Обработка ответа с множественным выбором"""
    data = await state.get_data()
    test_id = data["current_test_id"]
    current_question = data["current_question"]
    score = data["score"]
    answers = data.get("answers", [])

    test = data_manager.get_test(test_id)
    question = test["questions"][current_question]
    
    # Получаем выбранные варианты
    selected_answers = [question["options"][i] for i in selected_indices]
    correct_answers = question.get("answer", [])
    
    # Проверяем: все ли правильные выбраны и нет ли неправильных
    selected_set = set(selected_answers)
    correct_set = set(correct_answers)
    is_correct = selected_set == correct_set
    
    if is_correct:
        score += 1

    answers.append({
        "question": question["text"],
        "user_answer": selected_answers,
        "correct_answer": correct_answers,
        "is_correct": is_correct,
        "type": "multiple"
    })

    # Очищаем выбранные варианты
    await state.update_data(selected_options=None)

    # Следующий вопрос или завершение
    if current_question + 1 < len(test["questions"]):
        await state.update_data(
            current_question=current_question + 1,
            score=score,
            answers=answers
        )
        next_question = test["questions"][current_question + 1]
        await show_question(callback.message, next_question, current_question + 2, len(test["questions"]))
    else:
        # Завершение теста
        await state.clear()
        total = len(test["questions"])
        data_manager.save_result(callback.from_user.id, test_id, score, total, answers)

        percentage = round(score / total * 100, 1)
        await callback.message.answer(
            f"<b>✅ Тест завершён!</b>\n\n"
            f"Твой результат: <b>{score} из {total}</b> ({percentage}%)\n\n"
            f"Выбери действие в меню:",
            reply_markup=get_main_keyboard(data_manager.is_admin(callback.from_user.id))
        )


@router.message(TakeTest.in_progress)
async def process_test_answer(message: Message, state: FSMContext):
    """Обработка ответа на вопрос теста (одиночный выбор)"""
    data = await state.get_data()
    test_id = data["current_test_id"]
    current_question = data["current_question"]
    score = data["score"]
    answers = data.get("answers", [])

    test = data_manager.get_test(test_id)
    question = test["questions"][current_question]
    
    q_type = question.get("type", "single")

    # Если вопрос с множественным выбором, игнорируем текст
    if q_type == "multiple" or isinstance(question.get("answer"), list):
        await message.answer("<i>Для этого вопроса используйте кнопки выше</i>")
        return

    user_answer = message.text.strip()
    correct_answer = question["answer"]
    
    # Для совместимости: если answer это список (старые тесты)
    if isinstance(correct_answer, list):
        await message.answer("<i>Для этого вопроса используйте кнопки выше</i>")
        return
    
    is_correct = user_answer.lower() == correct_answer.lower()

    if is_correct:
        score += 1

    answers.append({
        "question": question["text"],
        "user_answer": user_answer,
        "correct_answer": question["answer"],
        "is_correct": is_correct,
        "type": "single"
    })

    # Следующий вопрос или завершение
    if current_question + 1 < len(test["questions"]):
        await state.update_data(
            current_question=current_question + 1,
            score=score,
            answers=answers
        )
        next_question = test["questions"][current_question + 1]
        await show_question(message, next_question, current_question + 2, len(test["questions"]))
    else:
        # Завершение теста
        await state.clear()
        total = len(test["questions"])
        data_manager.save_result(message.from_user.id, test_id, score, total, answers)

        percentage = round(score / total * 100, 1)
        await message.answer(
            f"<b>✅ Тест завершён!</b>\n\n"
            f"Твой результат: <b>{score} из {total}</b> ({percentage}%)\n\n"
            f"Выбери действие в меню:",
            reply_markup=get_main_keyboard(data_manager.is_admin(message.from_user.id))
        )


# === Таблица лидеров ===
@router.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: Message):
    """Показать таблицу лидеров"""
    tests = data_manager.get_tests()
    
    if not tests:
        await message.answer("Пока нет доступных тестов.")
        return
    
    # Создаём inline клавиатуру с выбором теста
    buttons = []
    for test_id, test in tests.items():
        buttons.append([InlineKeyboardButton(
            text=test["title"],
            callback_data=f"leaderboard_{test_id}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите тест для просмотра таблицы лидеров:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("leaderboard_"))
async def show_test_leaderboard(callback: CallbackQuery):
    """Показать таблицу лидеров для конкретного теста"""
    test_id = callback.data.replace("leaderboard_", "")
    test = data_manager.get_test(test_id)

    if not test:
        await callback.answer("Тест не найден", show_alert=True)
        return

    leaderboard = data_manager.get_leaderboard(test_id)

    if not leaderboard:
        await callback.message.answer("Пока нет результатов для этого теста.")
        await callback.answer()
        return

    text = f"<b>🏆 Таблица лидеров: {test['title']}</b>\n"
    text += "<i>(показан лучший результат для каждого пользователя)</i>\n\n"

    for i, entry in enumerate(leaderboard, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} <b>{entry['name']}</b> — {entry['score']}/{entry['total']} ({entry['percentage']}%)\n"
        # Форматируем дату в MSK
        completed_at = entry.get('completed_at', '')
        if completed_at:
            formatted_date = data_manager.format_date_msk(completed_at)
            text += f"   📅 {formatted_date}\n\n"
        else:
            text += f"   📅 {entry['date']} в {entry['time']}\n\n"

    await callback.message.answer(text)
    await callback.answer()


# === Мои результаты ===
@router.message(F.text == "📊 Мои результаты")
async def show_my_results(message: Message):
    """Показать результаты пользователя"""
    user_id = message.from_user.id
    results = data_manager.get_user_results(user_id)

    if not results:
        await message.answer("У тебя пока нет пройденных тестов.")
        return

    text = "<b>📊 Твои результаты:</b>\n\n"
    for r in results:
        test = data_manager.get_test(r["test_id"])
        test_name = test["title"] if test else f"Тест #{r['test_id']}"
        # Форматируем дату в MSK
        date = data_manager.format_date_msk(r["completed_at"])
        text += f"<b>{test_name}</b>\n"
        text += f"Результат: {r['score']}/{r['total']} ({r['percentage']}%)\n"
        text += f"Дата: {date}\n\n"

    await message.answer(text)


# === Создание теста (для администраторов) ===
@router.message(F.text == "➕ Создать тест")
async def cmd_create_test(message: Message, state: FSMContext):
    """Начать создание теста"""
    if not data_manager.is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return

    await message.answer(
        "<b>Создание нового теста</b>\n\n"
        "Введите название теста:"
    )
    await message.answer("Нажмите /cancel для отмены")
    await state.set_state(CreateTest.waiting_for_title)


@router.message(CreateTest.waiting_for_title)
async def process_test_title(message: Message, state: FSMContext):
    """Обработка названия теста"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Создание теста отменено.")
        return
    
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("Название слишком короткое. Введите корректное название:")
        return
    
    await state.update_data(title=title)
    await message.answer(
        f"Название сохранено: <b>{title}</b>\n\n"
        "Теперь введите описание теста (или напишите 'пропустить' чтобы перейти к вопросам):"
    )
    await state.set_state(CreateTest.waiting_for_description)


@router.message(CreateTest.waiting_for_description)
async def process_test_description(message: Message, state: FSMContext):
    """Обработка описания теста"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Создание теста отменено.")
        return
    
    description = message.text.strip()
    if description.lower() == "пропустить":
        description = ""
    
    await state.update_data(description=description, questions=[])
    await message.answer(
        f"Описание сохранено.\n\n"
        "<b>Добавление вопросов</b>\n\n"
        "Теперь введите текст первого вопроса:"
    )
    await state.set_state(CreateTest.waiting_for_question_text)


@router.message(CreateTest.waiting_for_question_text)
async def process_question_text(message: Message, state: FSMContext):
    """Обработка текста вопроса"""
    if message.text == "/cancel":
        data = await state.get_data()
        if data.get("questions"):
            # Сохраняем тест с имеющимися вопросами
            await save_test_data(message.from_user.id, state)
            return
        await state.clear()
        await message.answer("Создание теста отменено.")
        return
    
    await state.update_data(current_question_text=message.text.strip())
    await message.answer(
        f"Вопрос сохранён.\n\n"
        "Теперь введите <b>правильный ответ</b> на этот вопрос:"
    )
    await state.set_state(CreateTest.waiting_for_answer)


@router.message(CreateTest.waiting_for_answer)
async def process_question_answer(message: Message, state: FSMContext):
    """Обработка правильного ответа"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Создание теста отменено.")
        return
    
    data = await state.get_data()
    questions = data.get("questions", [])
    
    questions.append({
        "text": data["current_question_text"],
        "answer": message.text.strip()
    })
    
    await state.update_data(questions=questions, current_question_text=None)
    
    # Создаём клавиатуру для выбора
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё вопрос", callback_data="add_more_question")],
        [InlineKeyboardButton(text="✅ Завершить создание", callback_data="finish_test_creation")]
    ])
    
    await message.answer(
        f"Вопрос добавлен! Всего вопросов: {len(questions)}\n\n"
        "Что делаем дальше?",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "add_more_question")
async def add_more_questions(callback: CallbackQuery, state: FSMContext):
    """Добавление ещё одного вопроса"""
    await callback.message.answer("Введите текст следующего вопроса:")
    await state.set_state(CreateTest.waiting_for_question_text)
    await callback.answer()


@router.callback_query(F.data == "finish_test_creation")
async def finish_creation(callback: CallbackQuery, state: FSMContext):
    """Завершение создания теста"""
    await save_test_data(callback.from_user.id, state)
    await callback.answer()


async def save_test_data(user_id: int, state: FSMContext):
    """Сохранение созданного теста"""
    data = await state.get_data()
    
    if not data.get("questions"):
        await bot.send_message(user_id, "Тест должен содержать хотя бы один вопрос.")
        await state.clear()
        return
    
    test_id = data_manager.generate_test_id()
    test_data = {
        "title": data["title"],
        "description": data.get("description", ""),
        "questions": data["questions"],
        "created_by": user_id,
        "created_at": data_manager.datetime.now().isoformat()
    }
    
    data_manager.save_test(test_id, test_data)
    await state.clear()
    
    await bot.send_message(
        user_id,
        f"<b>✅ Тест создан!</b>\n\n"
        f"ID теста: <code>{test_id}</code>\n"
        f"Название: {data['title']}\n"
        f"Вопросов: {len(data['questions'])}\n\n"
        f"Теперь пользователи могут проходить этот тест."
    )


# === Отмена ===
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущего действия"""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "Действие отменено.",
            reply_markup=get_main_keyboard(data_manager.is_admin(message.from_user.id))
        )


# === Управление активностью тестов (для администраторов) ===
@router.message(Command("toggle_test"))
async def cmd_toggle_test(message: Message):
    """Переключить статус активности теста"""
    if not data_manager.is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return

    args = message.text.split()
    
    # Если указан ID теста
    if len(args) > 1:
        test_id = args[1].strip()
        await toggle_test_by_id(message, test_id)
        return
    
    # Показываем список тестов с кнопками
    tests = data_manager.get_tests()
    if not tests:
        await message.answer("Нет тестов для управления.")
        return

    text = "<b>📊 Управление тестами</b>\n\n"
    text += "Нажмите на кнопку для переключения статуса:\n\n"
    
    buttons = []
    for test_id, test in tests.items():
        status = "🟢" if test.get("active", True) else "🔴"
        buttons.append([InlineKeyboardButton(
            text=f"{status} {test['title']}",
            callback_data=f"toggle_{test_id}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text += "<i>Или используйте команду: /toggle_test &lt;ID&gt;</i>"
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("toggle_"))
async def callback_toggle_test(callback: CallbackQuery):
    """Переключение статуса теста через callback"""
    if not data_manager.is_admin(callback.from_user.id):
        await callback.answer("Доступно только администраторам", show_alert=True)
        return
    
    test_id = callback.data.replace("toggle_", "")
    await toggle_test_by_id(callback.message, test_id)
    await callback.answer()


async def toggle_test_by_id(message: Message, test_id: str):
    """Переключить статус теста по ID"""
    try:
        test = data_manager.get_test(test_id)
        if not test:
            await message.answer(f"❌ Тест с ID <code>{test_id}</code> не найден.")
            return

        new_status = data_manager.toggle_test_active(test_id)

        if new_status is None:
            await message.answer("❌ Ошибка при переключении статуса.")
            return

        status_text = "🟢 <b>Активен</b>" if new_status else "🔴 <b>Отключён</b>"
        await message.answer(
            f"✅ Статус теста изменён!\n\n"
            f"<b>{test['title']}</b> (ID: {test_id})\n"
            f"Новый статус: {status_text}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


# === Удаление теста (для администраторов) ===
@router.message(Command("delete_test"))
async def cmd_delete_test(message: Message):
    """Удалить тест"""
    if not data_manager.is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return

    args = message.text.split()
    
    # Если указан ID теста
    if len(args) > 1:
        test_id = args[1].strip()
        await delete_test_by_id(message, test_id)
        return
    
    # Показываем список тестов с кнопками
    tests = data_manager.get_tests()
    if not tests:
        await message.answer("Нет тестов для удаления.")
        return

    text = "<b>🗑️ Удаление тестов</b>\n\n"
    text += "Нажмите на кнопку для удаления теста:\n\n"
    
    buttons = []
    for test_id, test in tests.items():
        buttons.append([InlineKeyboardButton(
            text=f"❌ {test['title']}",
            callback_data=f"delete_{test_id}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text += "<i>Или используйте команду: /delete_test &lt;ID&gt;</i>"
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("delete_"))
async def callback_delete_test(callback: CallbackQuery):
    """Удаление теста через callback"""
    if not data_manager.is_admin(callback.from_user.id):
        await callback.answer("Доступно только администраторам", show_alert=True)
        return
    
    test_id = callback.data.replace("delete_", "")
    
    # Показываем подтверждение
    test = data_manager.get_test(test_id)
    if not test:
        await callback.answer("Тест не найден", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{test_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")]
    ])
    
    await callback.message.answer(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены что хотите удалить тест:\n"
        f"<b>{test['title']}</b> (ID: {test_id})\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_test(callback: CallbackQuery):
    """Подтверждение удаления теста"""
    if not data_manager.is_admin(callback.from_user.id):
        await callback.answer("Доступно только администраторам", show_alert=True)
        return
    
    test_id = callback.data.replace("confirm_delete_", "")
    
    success = data_manager.delete_test(test_id)
    
    if success:
        await callback.message.answer(f"✅ Тест <b>{test_id}</b> успешно удалён!")
        await callback.message.delete()  # Удаляем сообщение с подтверждением
    else:
        await callback.answer("Ошибка при удалении", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete_test(callback: CallbackQuery):
    """Отмена удаления теста"""
    await callback.message.delete()
    await callback.answer("Удаление отменено")


# === Управление правами администратора (только для существующих админов) ===
@router.message(Command("set_admin"))
async def cmd_set_admin(message: Message):
    """Назначить или снять права администратора с пользователя"""
    # Проверяем, что текущий пользователь уже администратор
    if not data_manager.is_admin(message.from_user.id):
        return  # Тихо игнорируем для безопасности

    args = message.text.split()
    if len(args) != 3:
        await message.answer(
            "Использование: <code>/set_admin &lt;user_id&gt; &lt;0|1&gt;</code>\n\n"
            "Примеры:\n"
            "<code>/set_admin 123456789 1</code> — назначить администратором\n"
            "<code>/set_admin 123456789 0</code> — снять права администратора"
        )
        return

    try:
        user_id = int(args[1])
        admin_status = int(args[2])
        
        if admin_status not in (0, 1):
            await message.answer("Статус должен быть 0 или 1")
            return
        
        user = data_manager.get_user(user_id)
        if not user:
            await message.answer(f"Пользователь с ID {user_id} не найден")
            return
        
        data_manager.set_admin_status(user_id, admin_status == 1)
        
        status_text = "🟢 назначен администратором" if admin_status else "🔴 сняты права администратора"
        await message.answer(
            f"✅ Права изменены!\n\n"
            f"Пользователь: {user['name']} (ID: {user_id})\n"
            f"Статус: {status_text}"
        )
    except ValueError:
        await message.answer("Неверный формат. Используйте числовые значения.")


# === Загрузка теста из JSON (для администраторов) ===
@router.message(Command("load_test"))
async def cmd_load_test(message: Message):
    """Загрузка теста из JSON"""
    if not data_manager.is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return
    
    await message.answer(
        "<b>📥 Загрузка теста из JSON</b>\n\n"
        "Отправьте JSON файл с тестом или вставьте его содержимое сообщением.\n\n"
        "Формат JSON:\n"
        "<pre>{{\n"
        '  "title": "Название теста",\n'
        '  "description": "Описание",\n'
        '  "questions": [\n'
        '    {{"text": "Вопрос 1", "answer": "Ответ 1"}},\n'
        '    {{"text": "Вопрос 2", "answer": "Ответ 2"}}\n'
        "  ]\n"
        "}}</pre>\n\n"
        "Используйте конструктор: <code>test_builder.html</code>"
    )


@router.message(F.document)
async def handle_document(message: Message):
    """Обработка загруженного файла"""
    if not data_manager.is_admin(message.from_user.id):
        return
    
    if message.document.file_name.endswith('.json'):
        # Скачиваем файл
        file = await bot.get_file(message.document.file_id)
        file_content = await bot.download_file(file.file_path)
        
        try:
            import json
            test_data = json.loads(file_content.read().decode('utf-8'))
            await process_test_json(message, test_data)
        except json.JSONDecodeError:
            await message.answer("❌ Ошибка: Неверный формат JSON файла.")
        except Exception as e:
            await message.answer(f"❌ Ошибка при чтении файла: {e}")


@router.message(F.text)
async def handle_json_text(message: Message, state: FSMContext):
    """Обработка JSON в текстовом виде"""
    if not data_manager.is_admin(message.from_user.id):
        return
    
    # Проверяем, не находится ли пользователь в другом состоянии (создание теста, прохождение)
    current_state = await state.get_state()
    if current_state:
        return  # Пропускаем, если пользователь в процессе создания/прохождения теста
    
    text = message.text.strip()
    if text.startswith('{') and text.endswith('}'):
        try:
            import json
            test_data = json.loads(text)
            await process_test_json(message, test_data)
        except json.JSONDecodeError:
            pass  # Не JSON, игнорируем


async def process_test_json(message: Message, test_data: dict):
    """Обработка данных теста из JSON"""
    # Валидация
    if not test_data.get("title"):
        await message.answer("❌ Ошибка: Отсутствует поле 'title'")
        return
    
    if not test_data.get("questions") or not isinstance(test_data["questions"], list):
        await message.answer("❌ Ошибка: Отсутствует или неверно поле 'questions'")
        return
    
    # Проверка вопросов
    for i, q in enumerate(test_data["questions"]):
        if not q.get("text") or not q.get("answer"):
            await message.answer(f"❌ Ошибка: Вопрос #{i+1} не содержит 'text' или 'answer'")
            return
    
    # Сохранение теста
    test_id = data_manager.generate_test_id()
    test_data_full = {
        "title": test_data["title"],
        "description": test_data.get("description", "Без описания"),
        "questions": test_data["questions"],
        "created_by": message.from_user.id,
        "created_at": data_manager.datetime.now().isoformat()
    }
    
    data_manager.save_test(test_id, test_data_full)
    
    await message.answer(
        f"<b>✅ Тест загружен!</b>\n\n"
        f"ID теста: <code>{test_id}</code>\n"
        f"Название: {test_data['title']}\n"
        f"Вопросов: {len(test_data['questions'])}\n\n"
        f"Теперь пользователи могут проходить этот тест."
    )


# === Запуск бота ===
async def main():
    """Запуск бота"""
    # Проверка конфигурации
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ОШИБКА: Укажите токен бота в config.py")
        print("Получите токен у @BotFather в Telegram")
        return
    
    if config.ADMIN_IDS == [123456789]:
        print("⚠️ ВНИМАНИЕ: Укажите ваши Telegram ID в config.py (ADMIN_IDS)")
    
    print("🤖 Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
