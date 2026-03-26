"""Модуль для работы с данными на SQLite"""
import sqlite3
import json
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
import config

# Настройка логирования
logger = logging.getLogger(__name__)

# Часовой пояс MSK (UTC+3)
MSK_TZ = timezone(timedelta(hours=3))


def get_now_msk() -> str:
    """Получить текущее время в формате ISO для MSK (UTC+3)"""
    return datetime.now(MSK_TZ).isoformat()


def format_date_msk(iso_date: str) -> str:
    """Форматировать дату из ISO в читаемый вид MSK"""
    try:
        dt = datetime.fromisoformat(iso_date)
        # Если нет timezone info, считаем что это UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Конвертируем в MSK
        dt_msk = dt.astimezone(MSK_TZ)
        return dt_msk.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date[:16].replace("T", " ")


# Получаем абсолютный путь к директории проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Проверяем наличие /data (для persistence mount)
if os.path.exists("/data"):
    DATA_DIR = "/data"
    logger.info("Using /data for persistence mount")
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")
    logger.info("Using local data directory")

DB_FILE = os.path.join(DATA_DIR, "bot.db")


def get_connection():
    """Получить соединение с базой данных"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализировать базу данных"""
    logger.info(f"Initializing database: {DB_FILE}")
    conn = get_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            admin INTEGER DEFAULT 0,
            registered_at TEXT,
            admin_updated_at TEXT
        )
    """)
    
    # Таблица тестов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            test_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            active INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    # Таблица вопросов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id TEXT NOT NULL,
            question_type TEXT DEFAULT 'single',
            text TEXT NOT NULL,
            answer TEXT,
            options TEXT,
            FOREIGN KEY (test_id) REFERENCES tests(test_id) ON DELETE CASCADE
        )
    """)
    
    # Таблица результатов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            test_id TEXT NOT NULL,
            score INTEGER,
            total INTEGER,
            percentage REAL,
            answers TEXT,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(telegram_id),
            FOREIGN KEY (test_id) REFERENCES tests(test_id)
        )
    """)
    
    # Индексы для ускорения
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_user ON results(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_test ON results(test_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_test ON questions(test_id)")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


# === Пользователи ===
def get_user(user_id: int) -> Optional[Dict]:
    """Получить пользователя по ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def is_name_taken(name: str) -> bool:
    """Проверить, занято ли имя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(name) = LOWER(?)", (name.strip(),))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def get_user_by_name(name: str) -> Optional[Dict]:
    """Получить пользователя по имени"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(name) = LOWER(?)", (name.strip(),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def save_user(user_id: int, name: str):
    """Сохранить или обновить пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем существующего пользователя
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    existing = cursor.fetchone()
    
    now = get_now_msk()
    
    if existing:
        # Обновляем, сохраняя admin статус
        cursor.execute("""
            UPDATE users 
            SET name = ?
            WHERE telegram_id = ?
        """, (name, user_id))
        logger.info(f"Updated user: {user_id}, name: {name}, admin={existing['admin']}")
    else:
        # Создаём нового
        cursor.execute("""
            INSERT INTO users (telegram_id, name, registered_at)
            VALUES (?, ?, ?)
        """, (user_id, name, now))
        logger.info(f"Created user: {user_id}, name: {name}")
    
    conn.commit()
    conn.close()
    
    # Проверяем что сохранилось
    verify_conn = get_connection()
    verify_cursor = verify_conn.cursor()
    verify_cursor.execute("SELECT name, admin FROM users WHERE telegram_id = ?", (user_id,))
    saved = verify_cursor.fetchone()
    verify_conn.close()
    
    if saved:
        logger.info(f"Verified save: user_id={user_id}, name={saved['name']}, admin={saved['admin']}")
    else:
        logger.error(f"FAILED TO SAVE: user_id={user_id}")


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    user = get_user(user_id)
    if user:
        return bool(user.get("admin", 0))
    # Fallback на ADMIN_IDS из config
    return user_id in config.ADMIN_IDS


def set_admin_status(user_id: int, admin: bool) -> bool:
    """Установить статус администратора"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        return False
    
    cursor.execute("""
        UPDATE users 
        SET admin = ?, admin_updated_at = ?
        WHERE telegram_id = ?
    """, (1 if admin else 0, get_now_msk(), user_id))
    
    conn.commit()
    conn.close()
    logger.info(f"Set admin={admin} for user {user_id}")
    return True


def get_all_admins() -> List[Dict]:
    """Получить всех администраторов"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE admin = 1")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# === Тесты ===
def get_tests(only_active: bool = False) -> Dict[str, Dict]:
    """Получить все тесты с вопросами"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if only_active:
        cursor.execute("SELECT * FROM tests WHERE active = 1")
    else:
        cursor.execute("SELECT * FROM tests")
    
    tests_rows = cursor.fetchall()
    tests = {}
    
    for test in tests_rows:
        test_id = test["test_id"]
        test_dict = dict(test)
        
        # Получаем вопросы
        cursor.execute("SELECT * FROM questions WHERE test_id = ?", (test_id,))
        questions = []
        for q in cursor.fetchall():
            q_dict = dict(q)
            # Парсим options из JSON
            if q_dict.get("options"):
                q_dict["options"] = json.loads(q_dict["options"])
            # Парсим answer для multiple choice
            if q_dict.get("answer") and q_dict.get("question_type") == "multiple":
                try:
                    q_dict["answer"] = json.loads(q_dict["answer"])
                except:
                    pass
            questions.append(q_dict)
        
        test_dict["questions"] = questions
        tests[test_id] = test_dict
    
    conn.close()
    return tests


def generate_test_id() -> str:
    """Сгенерировать уникальный ID для теста"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Получаем максимальный ID
    cursor.execute("SELECT MAX(CAST(test_id AS INTEGER)) FROM tests")
    row = cursor.fetchone()
    max_id = row[0] if row and row[0] else 0
    
    conn.close()
    return str(max_id + 1)


def save_test(test_id: str, test_data: Dict):
    """Сохранить тест"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = get_now_msk()
    
    # Проверяем существует ли тест
    cursor.execute("SELECT * FROM tests WHERE test_id = ?", (test_id,))
    exists = cursor.fetchone()
    
    if exists:
        cursor.execute("""
            UPDATE tests 
            SET title = ?, description = ?, active = ?, updated_at = ?
            WHERE test_id = ?
        """, (test_data["title"], test_data.get("description", ""), 
              1 if test_data.get("active", True) else 0, now, test_id))
        
        # Удаляем старые вопросы
        cursor.execute("DELETE FROM questions WHERE test_id = ?", (test_id,))
    else:
        cursor.execute("""
            INSERT INTO tests (test_id, title, description, active, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (test_id, test_data["title"], test_data.get("description", ""),
              1 if test_data.get("active", True) else 0,
              test_data.get("created_by"), now))
    
    # Добавляем вопросы
    for q in test_data.get("questions", []):
        options = None
        answer = q.get("answer")
        
        # Сериализуем options и answer для multiple choice
        if q.get("options"):
            options = json.dumps(q["options"], ensure_ascii=False)
        if q.get("type") == "multiple" and isinstance(answer, list):
            answer = json.dumps(answer, ensure_ascii=False)
        
        cursor.execute("""
            INSERT INTO questions (test_id, question_type, text, answer, options)
            VALUES (?, ?, ?, ?, ?)
        """, (test_id, q.get("type", "single"), q["text"], answer, options))
    
    conn.commit()
    conn.close()
    logger.info(f"Saved test: {test_id}")


def get_test(test_id: str) -> Optional[Dict]:
    """Получить тест по ID"""
    tests = get_tests()
    return tests.get(test_id)


def toggle_test_active(test_id: str) -> Optional[bool]:
    """Переключить статус активности теста"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT active FROM tests WHERE test_id = ?", (test_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
    
    new_status = 0 if row["active"] else 1
    cursor.execute("""
        UPDATE tests 
        SET active = ?, updated_at = ?
        WHERE test_id = ?
    """, (new_status, get_now_msk(), test_id))
    
    conn.commit()
    conn.close()
    return bool(new_status)


def set_test_active(test_id: str, active: bool) -> bool:
    """Установить статус активности теста"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tests WHERE test_id = ?", (test_id,))
    if not cursor.fetchone():
        conn.close()
        return False
    
    cursor.execute("""
        UPDATE tests 
        SET active = ?, updated_at = ?
        WHERE test_id = ?
    """, (1 if active else 0, get_now_msk(), test_id))
    
    conn.commit()
    conn.close()
    return True


def delete_test(test_id: str) -> bool:
    """Удалить тест"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tests WHERE test_id = ?", (test_id,))
    if not cursor.fetchone():
        conn.close()
        return False
    
    # Вопросы удалятся каскадно
    cursor.execute("DELETE FROM tests WHERE test_id = ?", (test_id,))
    
    conn.commit()
    conn.close()
    return True


# === Результаты ===
def get_results() -> List[Dict]:
    """Получить все результаты"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM results ORDER BY completed_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        # Парсим answers из JSON
        if r.get("answers"):
            r["answers"] = json.loads(r["answers"])
        results.append(r)
    
    return results


def save_result(user_id: int, test_id: str, score: int, total: int, answers: List[Dict]):
    """Сохранить результат теста"""
    conn = get_connection()
    cursor = conn.cursor()
    
    percentage = round(score / total * 100, 1) if total > 0 else 0
    now = get_now_msk()
    answers_json = json.dumps(answers, ensure_ascii=False)
    
    cursor.execute("""
        INSERT INTO results (user_id, test_id, score, total, percentage, answers, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, test_id, score, total, percentage, answers_json, now))
    
    conn.commit()
    conn.close()
    
    return {
        "user_id": user_id,
        "test_id": test_id,
        "score": score,
        "total": total,
        "percentage": percentage,
        "answers": answers,
        "completed_at": now
    }


def get_test_results(test_id: str) -> List[Dict]:
    """Получить результаты конкретного теста"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM results WHERE test_id = ? ORDER BY percentage DESC", (test_id,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        if r.get("answers"):
            r["answers"] = json.loads(r["answers"])
        results.append(r)
    
    return results


def get_user_results(user_id: int) -> List[Dict]:
    """Получить результаты пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM results WHERE user_id = ? ORDER BY completed_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        if r.get("answers"):
            r["answers"] = json.loads(r["answers"])
        results.append(r)
    
    return results


def get_leaderboard(test_id: str, limit: int = 10) -> List[Dict]:
    """Получить таблицу лидеров (лучший результат для каждого пользователя)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Получаем лучший результат для каждого пользователя
    cursor.execute("""
        SELECT r.user_id, MAX(r.percentage) as max_percentage
        FROM results r
        WHERE r.test_id = ?
        GROUP BY r.user_id
        ORDER BY max_percentage DESC
        LIMIT ?
    """, (test_id, limit))
    
    best_results = cursor.fetchall()
    leaderboard = []
    
    for row in best_results:
        user_id = row["user_id"]
        
        # Получаем полную информацию о лучшем результате
        cursor.execute("""
            SELECT * FROM results 
            WHERE user_id = ? AND test_id = ? AND percentage = ?
            ORDER BY completed_at DESC
            LIMIT 1
        """, (user_id, test_id, row["max_percentage"]))
        
        result = cursor.fetchone()
        if result:
            r = dict(result)
            
            # Получаем имя пользователя
            cursor.execute("SELECT name FROM users WHERE telegram_id = ?", (user_id,))
            user_row = cursor.fetchone()
            name = user_row["name"] if user_row else "Неизвестный"
            
            leaderboard.append({
                "name": name,
                "score": r["score"],
                "total": r["total"],
                "percentage": r["percentage"],
                "date": r["completed_at"][:10],
                "time": r["completed_at"][11:19],
                "completed_at": r["completed_at"]
            })
    
    conn.close()
    return leaderboard


# Инициализация БД при импорте
init_db()
