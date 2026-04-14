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
bot = Bot(token=config.BOT_TOKEN)
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


# === Состояния для тестов на вставку букв ===
class InsertTest(StatesGroup):
    choosing_test = State()  # Выбор теста
    answering = State()      # Прохождение теста
    review = State()         # Просмотр результатов


# === Состояния для создания тестов на вставку букв ===
class InsertTestBuilder(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_text = State()
    waiting_for_gap_answers = State()
    waiting_for_letters = State()
    adding_more_questions = State()


# === Вспомогательные функции ===
def get_main_keyboard(is_admin_user: bool) -> ReplyKeyboardMarkup:
    """Получить главное меню"""
    buttons = [
        [KeyboardButton(text="📋 Список тестов")],
        [KeyboardButton(text="✍️ Вставка букв")],
        [KeyboardButton(text="🏆 Таблица лидеров")],
        [KeyboardButton(text="📊 Мои результаты")],
    ]
    if is_admin_user:
        buttons.append([KeyboardButton(text="➕ Создать тест")])
        buttons.append([KeyboardButton(text="✍️ Создать вставку")])
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
            f"Привет, {user['name']}!\n"
            f"Твой Telegram ID: {user_id}\n\n"
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

    text = "📚 Справка по командам бота\n\n"

    text += "👤 Для всех пользователей:\n"
    text += "/start - Начать работу, узнать свой ID\n"
    text += "/help - Эта справка\n"
    text += "/ping - Проверка работоспособности\n"
    text += "/me - Мой профиль и статус\n"
    text += "/admin - Стать администратором (код: 6418237)\n"
    text += "✍️ Вставка букв - Пройти тест на вставку букв\n"
    text += "📋 Список тестов - Пройти обычный тест\n"
    text += "🏆 Таблица лидеров - Лучшие результаты\n"
    text += "📊 Мои результаты - История прохождений\n\n"

    if is_admin_user:
        text += "🔧 Для администраторов:\n"
        text += "➕ Создать тест - Создать обычный тест\n"
        text += "✍️ Создать вставку - Создать тест на вставку букв\n"
        text += "/edit_test - Редактор тестов (Mini App)\n"
        text += "/export_test <ID> - Экспорт теста в JSON\n"
        text += "/load_test - Загрузка теста из JSON\n"
        text += "/toggle_test - Вкл/выкл тесты\n"
        text += "/delete_test - Удалить тест\n"
        text += "/admins - Список администраторов\n"
        text += "/cancel - Отмена действия\n\n"

    text += "ℹ️ Дополнительно:\n"
    text += "• Тесты выбираются кнопками из списка\n"
    text += "• Вопросы бывают с одиночным и множественным выбором\n"
    text += "• В таблице лидеров показан лучший результат\n"
    text += "• Имена пользователей должны быть уникальны\n\n"

    text += "Бот: Русский язык - Тесты и проверка знаний"

    await message.answer(text)


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
    
    await message.answer(text)


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

    await message.answer(text)


# === ✍️ Вставка букв - Список тестов ===
@router.message(F.text == "✍️ Вставка букв")
@router.message(Command("insert_test"))
async def cmd_insert_test_list(message: Message):
    """Показать список тестов на вставку букв"""
    user = data_manager.get_user(message.from_user.id)

    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return

    # Получаем тесты с вопросами типа insert_letter
    tests = data_manager.get_tests(only_active=True)

    insert_tests = []
    for test_id, test in tests.items():
        insert_questions = [q for q in test.get("questions", []) if q.get("question_type") == "insert_letter"]
        if insert_questions:
            insert_tests.append({
                "test_id": test_id,
                "title": test["title"],
                "description": test.get("description", ""),
                "questions": insert_questions
            })

    if not insert_tests:
        await message.answer(
            "❌ Пока нет доступных тестов на вставку букв.\n\n"
            "Администраторы могут создать их через кнопку '✍️ Создать вставку'"
        )
        return

    # Создаём клавиатуру с тестами
    buttons = []
    for test in insert_tests:
        question_count = len(test["questions"])
        buttons.append([InlineKeyboardButton(
            text=f"📝 {test['title']} ({question_count} вопр.)",
            callback_data=f"insert_start_{test['test_id']}"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        "✍️ Вставка букв - Выберите тест\n\n"
        "Вам нужно будет вставлять пропущенные буквы в слова.\n"
        "Выберите тест из списка ниже:",
        reply_markup=keyboard
    )


# === Начало теста на вставку букв ===
@router.callback_query(F.data.startswith("insert_start_"))
async def start_insert_test(callback: CallbackQuery, state: FSMContext):
    """Начать прохождение теста на вставку букв"""
    test_id = callback.data.replace("insert_start_", "")
    test = data_manager.get_test(test_id)

    if not test:
        await callback.answer("Тест не найден", show_alert=True)
        return

    # Фильтруем только вопросы на вставку
    insert_questions = [q for q in test.get("questions", []) if q.get("question_type") == "insert_letter"]

    if not insert_questions:
        await callback.answer("В этом тесте нет вопросов на вставку букв", show_alert=True)
        return

    # Сохраняем состояние
    await state.update_data(
        user_id=callback.from_user.id,
        test_id=test_id,
        test_title=test["title"],
        questions=insert_questions,
        current_question=0,
        score=0,
        total_gaps=0,
        answers=[]
    )

    await state.set_state(InsertTest.answering)

    # Показываем первый вопрос
    await show_insert_question(callback.message, state)
    await callback.answer()


async def show_insert_question(message: Message, state: FSMContext):
    """Показать вопрос на вставку букв"""
    data = await state.get_data()
    questions = data.get("questions", [])
    current_idx = data.get("current_question", 0)

    if current_idx >= len(questions):
        await finish_insert_test(message, state)
        return

    question = questions[current_idx]
    question_num = current_idx + 1
    total_questions = len(questions)

    # Разбираем текст с пропусками
    text = question["text"]
    gaps = question.get("gaps", [])
    letters = question.get("letters", [])

    # Заменяем все .. на пронумерованные пропуски
    gap_number = 0
    parts = []
    last_end = 0
    
    while ".." in text[last_end:]:
        gap_pos = text.index("..", last_end)
        parts.append(text[last_end:gap_pos])
        gap_number += 1
        parts.append(f"【{gap_number}】")
        last_end = gap_pos + 2
    
    parts.append(text[last_end:])
    display_text = "".join(parts)

    # Создаём inline-кнопки с буквами
    buttons = []
    row = []
    for i, letter in enumerate(letters):
        row.append(InlineKeyboardButton(
            text=letter,
            callback_data=f"insert_letter_{i}"
        ))
        if len(row) == 4:  # Максимум 4 кнопки в ряду
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)

    # Кнопка подтверждения
    buttons.append([InlineKeyboardButton(
        text="✅ Готово",
        callback_data="insert_confirm"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Состояние для текущего вопроса
    await state.update_data(
        current_gaps={},  # {gap_index: letter}
        current_active_gap=0,  # Какой пропуск сейчас активен
        gaps=gaps,
        letters=letters,
        display_text=display_text
    )

    await message.answer(
        f"📝 <b>Вопрос {question_num} из {total_questions}</b>\n\n"
        f"{display_text}\n\n"
        f"👉 Сейчас заполняется пропуск 【{1}】\n"
        f"Выберите букву:",
        reply_markup=keyboard
    )


# === Выбор буквы ===
@router.callback_query(F.data.startswith("insert_letter_"))
async def select_insert_letter(callback: CallbackQuery, state: FSMContext):
    """Выбрать букву для текущего пропуска"""
    letter_idx = int(callback.data.replace("insert_letter_", ""))
    
    data = await state.get_data()
    current_active_gap = data.get("current_active_gap", 0)
    current_gaps = data.get("current_gaps", {})
    gaps = data.get("gaps", [])
    letters = data.get("letters", [])
    display_text = data.get("display_text", "")
    questions = data.get("questions", [])
    current_idx = data.get("current_question", 0)
    
    # Получаем букву по индексу
    if letter_idx >= len(letters):
        await callback.answer("⚠️ Ошибка выбора")
        return
    
    letter = letters[letter_idx]
    
    # Заполняем текущий пропуск
    current_gaps[current_active_gap] = letter
    next_gap = current_active_gap + 1
    
    # Обновляем текст с заполненными пропусками
    updated_text = display_text
    for gap_idx, gap_letter in current_gaps.items():
        updated_text = updated_text.replace(f"【{gap_idx + 1}】", f"[{gap_letter}]", 1)
    
    await state.update_data(
        current_gaps=current_gaps,
        current_active_gap=next_gap,
        display_text=updated_text
    )
    
    if next_gap < len(gaps):
        # Ещё есть пропуски - показываем обновлённый текст
        await callback.message.edit_text(
            f"📝 <b>Вопрос {current_idx + 1} из {len(questions)}</b>\n\n"
            f"{updated_text}\n\n"
            f"👉 Сейчас заполняется пропуск 【{next_gap + 1}】\n"
            f"Выберите букву:",
            reply_markup=callback.message.reply_markup
        )
        await callback.answer(f"✓ Буква '{letter}' вставлена")
    else:
        # Все пропуски заполнены
        await callback.message.edit_text(
            f"📝 <b>Вопрос {current_idx + 1} из {len(questions)}</b>\n\n"
            f"{updated_text}\n\n"
            f"✅ Все пропуски заполнены! Нажмите 'Готово' для проверки.",
            reply_markup=callback.message.reply_markup
        )
        await callback.answer(f"✓ Буква '{letter}' вставлена. Все пропуски заполнены!")


# === Подтверждение ответа ===
@router.callback_query(F.data == "insert_confirm")
async def confirm_insert_answer(callback: CallbackQuery, state: FSMContext):
    """Подтвердить ответ на вопрос"""
    data = await state.get_data()
    current_gaps = data.get("current_gaps", {})
    gaps = data.get("gaps", [])
    questions = data.get("questions", [])
    current_idx = data.get("current_question", 0)
    score = data.get("score", 0)
    answers = data.get("answers", [])

    # Проверяем все ли пропуски заполнены
    if None in current_gaps.values() or len(current_gaps) < len(gaps):
        await callback.answer("⚠️ Заполните все пропуски!", show_alert=True)
        return

    # Проверяем ответы
    question = questions[current_idx]
    correct_count = 0
    question_details = []

    for gap_idx, gap in enumerate(gaps):
        user_answer = current_gaps.get(gap_idx, "")
        correct_answer = gap.get("correct", "").lower()
        is_correct = user_answer.lower() == correct_answer

        if is_correct:
            correct_count += 1

        question_details.append({
            "gap_number": gap_idx + 1,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct
        })

    # Обновляем счёт
    score += correct_count
    answers.append({
        "question": question["text"],
        "correct": correct_count,
        "total": len(gaps),
        "details": question_details
    })

    total_gaps = data.get("total_gaps", 0) + len(gaps)

    await state.update_data(
        score=score,
        total_gaps=total_gaps,
        answers=answers,
        current_question=current_idx + 1
    )

    # Показываем результат и переходим к следующему
    result_text = f"✅ Правильно: {correct_count} из {len(gaps)}\n\n"
    for detail in question_details:
        icon = "✅" if detail["is_correct"] else "❌"
        result_text += f"{icon} Пропуск {detail['gap_number']}: {detail['user_answer']} (правильно: {detail['correct_answer']})\n"

    await callback.message.answer(result_text)

    # Следующий вопрос или завершение
    await show_insert_question(callback.message, state)
    await callback.answer()


async def finish_insert_test(message: Message, state: FSMContext):
    """Завершить тест на вставку букв"""
    data = await state.get_data()
    test_title = data.get("test_title", "Тест")
    score = data.get("score", 0)
    total_gaps = data.get("total_gaps", 0)
    answers = data.get("answers", [])
    user_id = data.get("user_id")

    percentage = round(score / total_gaps * 100, 1) if total_gaps > 0 else 0

    # Сохраняем результат
    data_manager.save_result(
        user_id,
        data.get("test_id", "insert"),
        score,
        total_gaps,
        answers
    )

    # Показываем итог
    emoji = "🏆" if percentage >= 80 else "👍" if percentage >= 60 else "📚"

    await message.answer(
        f"{emoji} Тест завершён!\n\n"
        f"{test_title}\n"
        f"Правильно: {score} из {total_gaps}\n"
        f"Процент: {percentage}%\n\n"
        f"Результат сохранён!",
        reply_markup=get_main_keyboard(data_manager.is_admin(message.from_user.id))
    )

    await state.clear()


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


# === Универсальный обработчик данных из Mini Apps ===
@router.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    """Обработка данных из всех Mini Apps"""
    try:
        import json
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        # === Обработка данных от редактора тестов ===
        if action == "get_tests_list":
            if not data_manager.is_admin(message.from_user.id):
                return

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

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📚 Обновить список", callback_data="refresh_tests")]
            ])
            await message.answer(
                "📋 Список тестов отправлен в редактор",
                reply_markup=keyboard
            )

        elif action == "create_test":
            if not data_manager.is_admin(message.from_user.id):
                return

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
            if not data_manager.is_admin(message.from_user.id):
                return

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

        # === Обработка запроса тестов на вставку букв ===
        elif action == "get_insert_tests":
            tests = data_manager.get_tests(only_active=True)
            insert_tests = []
            
            for test_id, test in tests.items():
                insert_questions = [q for q in test.get("questions", []) if q.get("question_type") == "insert_letter"]
                if insert_questions:
                    insert_tests.append({
                        "test_id": test_id,
                        "title": test["title"],
                        "description": test.get("description", ""),
                        "questions": insert_questions
                    })
            
            # В данной версии просто логируем
            logger.info(f"Requested insert tests: {len(insert_tests)} tests found")

        # === Обработка создания теста на вставку букв ===
        elif action == "create_insert_test":
            if not data_manager.is_admin(message.from_user.id):
                await message.answer("❌ Эта команда доступна только администраторам.")
                return

            title = data.get("title")
            description = data.get("description", "")
            questions = data.get("questions", [])

            if not title or not questions:
                await message.answer("❌ Ошибка: указаны не все данные")
                return

            test_id = data_manager.generate_test_id()
            test_data = {
                "title": title,
                "description": description,
                "active": data.get("active", True),
                "questions": questions,
                "created_by": message.from_user.id,
                "created_at": data_manager.get_now_msk()
            }

            data_manager.save_test(test_id, test_data)

            await message.answer(
                f"✅ <b>Тест на вставку букв создан!</b>\n\n"
                f"ID: <code>{test_id}</code>\n"
                f"Название: {title}\n"
                f"Вопросов: {len(questions)}\n\n"
                f"Пользователи могут проходить его через /insert_test"
            )

        # === Обработка результатов теста на вставку букв ===
        elif action == "submit_insert_test":
            user_id = message.from_user.id
            test_id = data.get("test_id")
            score = data.get("score", 0)
            total = data.get("total", 0)
            percentage = data.get("percentage", 0)

            result = data_manager.save_result(user_id, test_id, score, total, [{
                "type": "insert_letter",
                "score": score,
                "total": total,
                "answers": data.get("answers", {})
            }])

            emoji = "🏆" if percentage >= 80 else "👍" if percentage >= 60 else "📚"

            await message.answer(
                f"{emoji} <b>Результат сохранён!</b>\n\n"
                f"<b>{test_id}</b>\n"
                f"Правильно: {score} из {total}\n"
                f"Процент: {percentage}%\n\n"
                f"Результат добавлен в таблицу лидеров! 🏆"
            )

        # === Обработка результатов из старого Mini App (без action) ===
        elif "test_id" in data and "score" in data and "percentage" in data:
            user_id = message.from_user.id
            test_id = data.get("test_id")
            score = data.get("score", 0)
            total = data.get("total", 0)
            percentage = data.get("percentage", 0)

            data_manager.save_result(user_id, test_id, score, total, [{
                "type": "insert_letter",
                "score": score,
                "total": total,
                "answers": data.get("answers", {})
            }])

            emoji = "🏆" if percentage >= 80 else "👍" if percentage >= 60 else "📚"

            await message.answer(
                f"{emoji} <b>Результат сохранён!</b>\n\n"
                f"<b>{test_id}</b>\n"
                f"Правильно: {score} из {total}\n"
                f"Процент: {percentage}%\n\n"
                f"Результат добавлен в таблицу лидеров! 🏆"
            )

    except json.JSONDecodeError:
        # Это не JSON, игнорируем
        pass
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки данных: {e}")


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
    insert_questions = [q for q in test.get("questions", []) if q.get("question_type") == "insert_letter"]
    
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
    insert_questions = [q for q in test.get("questions", []) if q.get("question_type") == "insert_letter"]

    if not insert_questions or question_idx >= len(insert_questions):
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    question = insert_questions[question_idx]

    # Формируем данные для Mini App
    import json
    from urllib.parse import quote

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

    app_url = f"https://doctorseventop.github.io/RusTestBot/miniapp.html?data={quote(json.dumps(app_data))}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить", web_app={"url": app_url})]
    ])

    await callback.message.answer(
        f"📝 <b>{test['title']}</b>\n\n"
        f"Нажмите кнопку ниже чтобы начать:",
        reply_markup=keyboard
    )
    await callback.answer()


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

    text += f"Всего администраторов: {len(admins)}"
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
    """Показать список доступных тестов (только обычные, не вставка букв)"""
    tests = data_manager.get_tests(only_active=True)

    # Фильтруем - только тесты с обычными вопросами
    regular_tests = {}
    for test_id, test in tests.items():
        has_regular = any(q.get("question_type") != "insert_letter" for q in test.get("questions", []))
        if has_regular:
            regular_tests[test_id] = test

    if not regular_tests:
        await message.answer("Пока нет доступных тестов.")
        return

    text = "📚 Доступные тесты:\n\n"
    buttons = []

    for test_id, test in regular_tests.items():
        questions_count = len(test.get("questions", []))
        text += f"{test_id}. {test['title']}\n"
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
    gaps = question.get("gaps")
    letters = question.get("letters")

    # === insert_letter - показываем текст с пропусками и кнопки букв ===
    if q_type == "insert_letter" and gaps and letters:
        text = question["text"]
        
        # Заменяем .. на пронумерованные пропуски
        gap_number = 0
        parts = []
        last_end = 0
        
        while ".." in text[last_end:]:
            gap_pos = text.index("..", last_end)
            parts.append(text[last_end:gap_pos])
            gap_number += 1
            parts.append(f"【{gap_number}】")
            last_end = gap_pos + 2
        
        parts.append(text[last_end:])
        display_text = "".join(parts)

        # Создаём inline-кнопки с буквами
        buttons = []
        row = []
        for i, letter in enumerate(letters):
            row.append(InlineKeyboardButton(
                text=letter,
                callback_data=f"answer_option_{i}"
            ))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        # Кнопка "Готово"
        buttons.append([InlineKeyboardButton(
            text="✅ Готово",
            callback_data="answer_done"
        )])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer(
            f"<b>Вопрос {question_num} из {total}</b>\n\n"
            f"{display_text}\n\n"
            f"<i>Нажмите на пропуск, затем выберите букву:</i>",
            reply_markup=keyboard
        )
        return

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
    """Обработка ответа с множественным выбором или insert_letter"""
    data = await state.get_data()
    test_id = data["current_test_id"]
    current_question = data["current_question"]
    score = data.get("score", 0)
    answers = data.get("answers", [])

    test = data_manager.get_test(test_id)
    question = test["questions"][current_question]
    q_type = question.get("type", "single")

    # === insert_letter - проверяем буквы против gaps ===
    if q_type == "insert_letter":
        gaps = question.get("gaps", [])
        letters = question.get("letters", [])
        
        # Получаем выбранные буквы
        selected_letters = [letters[i] for i in selected_indices if i < len(letters)]
        correct_letters = [g["correct"] for g in gaps]
        
        # Сравниваем (порядок важен для insert_letter)
        is_correct = selected_letters == correct_letters
        
        if is_correct:
            score += 1

        answers.append({
            "question": question["text"],
            "user_answer": selected_letters,
            "correct_answer": correct_letters,
            "is_correct": is_correct,
            "type": "insert_letter"
        })

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
        return

    # === Множественный выбор ===
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

    text = f"🏆 Таблица лидеров: {test['title']}\n"
    text += "(показан лучший результат для каждого пользователя)\n\n"

    for i, entry in enumerate(leaderboard, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {entry['name']} — {entry['score']}/{entry['total']} ({entry['percentage']}%)\n"
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

    text = "📊 Твои результаты:\n\n"
    for r in results:
        test = data_manager.get_test(r["test_id"])
        test_name = test["title"] if test else f"Тест #{r['test_id']}"
        date = data_manager.format_date_msk(r["completed_at"])
        text += f"{test_name}\n"
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
        "📥 Загрузка теста из JSON\n\n"
        "Отправьте JSON файл с тестом или вставьте его содержимое сообщением.\n\n"
        "Формат JSON:\n"
        "```\n"
        "{\n"
        '  "title": "Название теста",\n'
        '  "description": "Описание",\n'
        '  "questions": [\n'
        '    {"text": "Вопрос 1", "answer": "Ответ 1"},\n'
        '    {"type": "insert_letter", "text": "Див..н",\n'
        '     "gaps": [{"position": 0, "correct": "а"}],\n'
        '     "letters": ["а", "о", "н"]}\n'
        "  ]\n"
        "}\n"
        "```\n\n"
        "Поддерживаются обычные тесты и тесты на вставку букв."
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


# === ✍️ Создать вставку (для администраторов) - ДОЛЖНО БЫТЬ ДО F.text ===
@router.message(F.text == "✍️ Создать вставку")
@router.message(Command("insert_builder"))
async def cmd_insert_builder(message: Message, state: FSMContext):
    """Начать создание теста на вставку букв"""
    logger.info(f"Получена команда создания вставки от пользователя {message.from_user.id}")
    
    if not data_manager.is_admin(message.from_user.id):
        await message.answer("❌ Эта команда доступна только администраторам.")
        return

    await message.answer(
        "✍️ <b>Создание теста на вставку букв</b>\n\n"
        "Введите название теста (например: Правописание -Н- и -НН-):"
    )
    await state.set_state(InsertTestBuilder.waiting_for_title)


@router.message(InsertTestBuilder.waiting_for_title)
async def process_insert_test_title(message: Message, state: FSMContext):
    """Обработка названия теста"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Создание теста отменено.", reply_markup=get_main_keyboard(True))
        return

    title = message.text.strip()
    if len(title) < 3:
        await message.answer("Название слишком короткое. Введите корректное название:")
        return

    await state.update_data(title=title, questions=[])
    await message.answer(
        f"✅ Название сохранено: <b>{title}</b>\n\n"
        f"Введите описание теста (или напишите 'пропустить'):"
    )
    await state.set_state(InsertTestBuilder.waiting_for_description)


@router.message(InsertTestBuilder.waiting_for_description)
async def process_insert_test_description(message: Message, state: FSMContext):
    """Обработка описания теста"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Создание теста отменено.", reply_markup=get_main_keyboard(True))
        return

    description = message.text.strip()
    if description.lower() == "пропустить":
        description = ""

    await state.update_data(description=description)
    await message.answer(
        f"✅ Описание сохранено.\n\n"
        f"<b>Добавление вопросов</b>\n\n"
        f"Введите текст с пропусками (используйте .. для пропусков):\n\n"
        f"<i>Пример: В комнате стоял див..н, который был украше.. узором.</i>"
    )
    await state.set_state(InsertTestBuilder.waiting_for_text)


@router.message(InsertTestBuilder.waiting_for_text)
async def process_insert_test_text(message: Message, state: FSMContext):
    """Обработка текста вопроса"""
    if message.text == "/cancel":
        data = await state.get_data()
        if data.get("questions"):
            await save_insert_test(message.from_user.id, state)
            return
        await state.clear()
        await message.answer("Создание теста отменено.", reply_markup=get_main_keyboard(True))
        return

    text = message.text.strip()
    
    # Проверяем что это не команда "пропустить"
    if text.lower() == "пропустить":
        await message.answer(
            "⚠️ На этом шаге нужно ввести текст вопроса с пропусками (..).\n\n"
            f"<i>Пример: В комнате стоял див..н, который был украше.. узором.</i>\n\n"
            f"Если хотите пропустить описание, это нужно было сделать на предыдущем шаге."
        )
        return
    
    if ".." not in text:
        await message.answer(
            "⚠️ Текст должен содержать минимум один пропуск (..).\n\n"
            f"<i>Пример: В комнате стоял див..н.</i>\n\n"
            f"Повторите ввод:"
        )
        return

    gap_count = text.count("..")
    await state.update_data(current_text=text, gap_count=gap_count)
    await message.answer(
        f"✅ Текст принят. Найдено пропусков: <b>{gap_count}</b>\n\n"
        f"Теперь введите правильные буквы для каждого пропуска через пробел:\n\n"
        f"<i>Пример: а н (для двух пропусков)</i>"
    )
    await state.set_state(InsertTestBuilder.waiting_for_gap_answers)


@router.message(InsertTestBuilder.waiting_for_gap_answers)
async def process_insert_gap_answers(message: Message, state: FSMContext):
    """Обработка правильных букв для пропусков"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Создание теста отменено.", reply_markup=get_main_keyboard(True))
        return

    answers = message.text.strip().lower().split()
    data = await state.get_data()
    gap_count = data.get("gap_count", 0)

    if len(answers) != gap_count:
        await message.answer(
            f"⚠️ Нужно ввести {gap_count} букв(ы) через пробел.\n\n"
            f"Повторите ввод:"
        )
        return

    await state.update_data(gap_answers=answers)
    await message.answer(
        f"✅ Правильные буквы сохранены.\n\n"
        f"Теперь введите варианты букв для выбора (минимум 2, через пробел):\n\n"
        f"<i>Пример: а о н е</i>\n\n"
        f"<i>Правильные буквы уже включены автоматически.</i>"
    )
    await state.set_state(InsertTestBuilder.waiting_for_letters)


@router.message(InsertTestBuilder.waiting_for_letters)
async def process_insert_letters(message: Message, state: FSMContext):
    """Обработка вариантов букв"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Создание теста отменено.", reply_markup=get_main_keyboard(True))
        return

    letters = message.text.strip().lower().split()
    data = await state.get_data()
    gap_answers = data.get("gap_answers", [])

    all_letters = set(letters + gap_answers)
    if len(all_letters) < 2:
        await message.answer("⚠️ Нужно минимум 2 варианта букв.\n\nПовторите ввод:")
        return

    questions = data.get("questions", [])
    questions.append({
        "type": "insert_letter",
        "text": data["current_text"],
        "gaps": [{"position": i, "correct": gap_answers[i]} for i in range(len(gap_answers))],
        "letters": sorted(list(all_letters)),
        "description": "Вставьте пропущенные буквы"
    })

    await state.update_data(questions=questions)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё вопрос", callback_data="insert_add_more")],
        [InlineKeyboardButton(text="✅ Завершить создание", callback_data="insert_finish")]
    ])

    await message.answer(
        f"✅ Вопрос добавлен! Всего вопросов: {len(questions)}\n\n"
        f"Что делаем дальше?",
        reply_markup=keyboard
    )
    await state.set_state(InsertTestBuilder.adding_more_questions)


@router.callback_query(F.data == "insert_add_more")
async def insert_add_more(callback: CallbackQuery, state: FSMContext):
    """Добавить ещё вопрос"""
    await callback.message.answer(
        f"Введите текст следующего вопроса (используйте .. для пропусков):\n\n"
        f"<i>Пример: Краше..ая корзина была поставле..а на стол.</i>"
    )
    await state.set_state(InsertTestBuilder.waiting_for_text)
    await callback.answer()


@router.callback_query(F.data == "insert_finish")
async def insert_finish(callback: CallbackQuery, state: FSMContext):
    """Завершить создание теста"""
    await save_insert_test(callback.from_user.id, state)
    await callback.answer()


async def save_insert_test(user_id: int, state: FSMContext):
    """Сохранить созданный тест"""
    data = await state.get_data()
    questions = data.get("questions", [])

    if not questions:
        await bot.send_message(user_id, "❌ Тест должен содержать хотя бы один вопрос.")
        await state.clear()
        return

    test_id = data_manager.generate_test_id()
    test_data = {
        "title": data["title"],
        "description": data.get("description", ""),
        "active": True,
        "questions": questions,
        "created_by": user_id,
        "created_at": data_manager.get_now_msk()
    }

    data_manager.save_test(test_id, test_data)
    await state.clear()

    await bot.send_message(
        user_id,
        f"✅ <b>Тест на вставку букв создан!</b>\n\n"
        f"ID теста: <code>{test_id}</code>\n"
        f"Название: {data['title']}\n"
        f"Вопросов: {len(questions)}\n\n"
        f"Теперь пользователи могут проходить этот тест через кнопку '✍️ Вставка букв'.",
        reply_markup=get_main_keyboard(data_manager.is_admin(user_id))
    )


@router.message(F.text)
async def handle_json_text(message: Message, state: FSMContext):
    """Обработка JSON в текстовом виде"""
    # Игнорируем кнопки меню
    if message.text in ["✍️ Создать вставку", "✍️ Вставка букв"]:
        return
    
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
        if not q.get("text"):
            await message.answer(f"❌ Ошибка: Вопрос #{i+1} не содержит 'text'")
            return
        
        q_type = q.get("type", "single")
        
        # Для insert_letter проверяем gaps и letters
        if q_type == "insert_letter":
            if not q.get("gaps"):
                await message.answer(f"❌ Ошибка: Вопрос #{i+1} (вставка букв) не содержит 'gaps'")
                return
            if not q.get("letters"):
                await message.answer(f"❌ Ошибка: Вопрос #{i+1} (вставка букв) не содержит 'letters'")
                return
        # Для обычных вопросов проверяем answer
        elif not q.get("answer"):
            await message.answer(f"❌ Ошибка: Вопрос #{i+1} не содержит 'answer'")
            return

    # Сохранение теста
    test_id = data_manager.generate_test_id()
    test_data_full = {
        "title": test_data["title"],
        "description": test_data.get("description", "Без описания"),
        "questions": test_data["questions"],
        "created_by": message.from_user.id,
        "created_at": data_manager.get_now_msk()
    }

    data_manager.save_test(test_id, test_data_full)
    
    # Считаем типы вопросов
    insert_count = sum(1 for q in test_data["questions"] if q.get("type") == "insert_letter")
    regular_count = len(test_data["questions"]) - insert_count

    type_info = ""
    if insert_count > 0:
        type_info += f"✍️ Вставка букв: {insert_count}\n"
    if regular_count > 0:
        type_info += f"📝 Обычные: {regular_count}\n"

    await message.answer(
        f"✅ <b>Тест загружен!</b>\n\n"
        f"ID теста: <code>{test_id}</code>\n"
        f"Название: {test_data['title']}\n"
        f"Вопросов: {len(test_data['questions'])}\n"
        f"{type_info}\n"
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
