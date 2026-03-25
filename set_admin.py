"""
Скрипт для назначения администратора вручную.
Запускать один раз для создания первого администратора.

Использование:
    python set_admin.py <telegram_id>

Пример:
    python set_admin.py 5153839634
"""
import sys
import os
from datetime import datetime

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_manager import get_connection, init_db, DATA_DIR

# Создаём директорию если нужно
os.makedirs(DATA_DIR, exist_ok=True)


def set_first_admin(user_id: int):
    """Назначить пользователя администратором"""
    print(f"Using data directory: {DATA_DIR}")
    init_db()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем существует ли пользователь
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    existing = cursor.fetchone()
    
    now = datetime.now().isoformat()
    
    if existing:
        # Обновляем статус
        cursor.execute("""
            UPDATE users 
            SET admin = 1, admin_updated_at = ?
            WHERE telegram_id = ?
        """, (now, user_id))
        print(f"✅ Пользователь {user_id} найден. Права администратора назначены.")
    else:
        # Создаём нового
        cursor.execute("""
            INSERT INTO users (telegram_id, name, admin, registered_at, admin_updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, f"Admin_{user_id}", 1, now, now))
        print(f"✅ Создан новый пользователь {user_id} с правами администратора.")
    
    conn.commit()
    conn.close()
    
    print(f"📁 База данных: {os.path.join(DATA_DIR, 'bot.db')}")
    print("\nТеперь перезапустите бота для применения изменений.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("❌ Использование: python set_admin.py <telegram_id>")
        print("\nПример: python set_admin.py 5153839634")
        sys.exit(1)
    
    try:
        admin_id = int(sys.argv[1])
        set_first_admin(admin_id)
    except ValueError:
        print("❌ Ошибка: Telegram ID должен быть числом")
        sys.exit(1)
