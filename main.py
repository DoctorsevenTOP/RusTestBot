"""Telegram бот для проверки знаний по русскому языку"""
import asyncio
import logging
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
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


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
    text += "📋 Список тестов - Пройти тест\n"
    text += "🏆 Таблица лидеров - Лучшие результаты\n"
    text += "📊 Мои результаты - История прохождений\n\n"

    if is_admin_user:
        text += "<b>🔧 Для администраторов:</b>\n"
        text += "➕ Создать тест - Интерактивное создание\n"
        text += "/load_test - Загрузка теста из JSON\n"
        text += "/toggle_test - Вкл/выкл тесты\n"
        text += "/toggle_test <code>&lt;ID&gt;</code> - Переключить статус теста\n"
        text += "/set_admin <code>&lt;ID&gt; &lt;0|1&gt;</code> - Права администратора\n"
        text += "/cancel - Отмена действия\n\n"

    text += "<b>ℹ️ Дополнительно:</b>\n"
    text += "• Тесты выбираются кнопками из списка\n"
    text += "• Вопросы бывают с одиночным и множественным выбором\n"
    text += "• В таблице лидеров показан лучший результат\n"
    text += "• Имена пользователей должны быть уникальны\n\n"

    text += "<i>Бот: Русский язык - Тесты и проверка знаний</i>"

    await message.answer(text, parse_mode="HTML")


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
    
    if q_type == "multiple" and question.get("options"):
        # Множественный выбор - создаём inline-кнопки
        buttons = []
        for i, option in enumerate(question["options"]):
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
    selected = data.get("selected_options", [])
    
    option_idx = int(callback.data.replace("answer_option_", ""))
    
    if option_idx in selected:
        selected.remove(option_idx)
    else:
        selected.append(option_idx)
    
    await state.update_data(selected_options=selected)
    await callback.answer(f"Выбрано: {len(selected)}")


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
    
    # Если вопрос с множественным выбором, игнорируем текст
    if question.get("type") == "multiple":
        await message.answer("<i>Для этого вопроса используйте кнопки выше</i>")
        return

    user_answer = message.text.strip()
    is_correct = user_answer.lower() == question["answer"].lower()

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
        date = r["completed_at"][:10]
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

    tests = data_manager.get_tests()
    if not tests:
        await message.answer("Нет тестов для управления.")
        return

    # Показываем список тестов с их статусом
    text = "<b>📊 Управление тестами</b>\n\n"
    text += "Отправьте <code>/toggle_test &lt;ID&gt;</code> для переключения статуса\n\n"
    
    for test_id, test in tests.items():
        status = "🟢 Активен" if test.get("active", True) else "🔴 Отключён"
        text += f"<b>{test_id}</b>. {test['title']} — {status}\n"
    
    text += "\n<i>Пример: /toggle_test 1</i>"
    await message.answer(text)


@router.message(F.text.startswith("/toggle_test "))
async def process_toggle_test(message: Message):
    """Обработка команды переключения теста"""
    if not data_manager.is_admin(message.from_user.id):
        return

    try:
        test_id = message.text.replace("/toggle_test ", "").strip()
        
        if not test_id:
            await message.answer("❌ Укажите ID теста. Пример: <code>/toggle_test 1</code>")
            return
        
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
