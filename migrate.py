"""
Скрипт для миграции данных из JSON в SQLite.
Запускать один раз при переходе на новую версию.

Использование:
    python migrate.py
"""
import sys
import os
import json

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_manager import (
    init_db, save_user, save_test, save_result, 
    set_admin_status, get_connection, DATA_DIR
)

# Локальная папка для старых JSON файлов
LOCAL_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def migrate_users():
    """Миграция пользователей из JSON"""
    users_file = os.path.join(LOCAL_DATA_DIR, "users.json")
    if not os.path.exists(users_file):
        print("⚠️ users.json не найден, пропускаем")
        return 0
    
    with open(users_file, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return 0
        users = json.loads(content)
    
    count = 0
    for user_id_str, user_data in users.items():
        user_id = int(user_id_str)
        save_user(user_id, user_data.get("name", "Unknown"))
        
        # Восстанавливаем admin статус
        if user_data.get("admin"):
            set_admin_status(user_id, True)
        
        # Восстанавливаем registered_at
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET registered_at = ?
            WHERE telegram_id = ?
        """, (user_data.get("registered_at"), user_id))
        conn.commit()
        conn.close()
        
        count += 1
    
    return count


def migrate_tests():
    """Миграция тестов из JSON"""
    tests_file = os.path.join(LOCAL_DATA_DIR, "tests.json")
    if not os.path.exists(tests_file):
        print("⚠️ tests.json не найден, пропускаем")
        return 0
    
    with open(tests_file, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return 0
        tests = json.loads(content)
    
    count = 0
    for test_id, test_data in tests.items():
        save_test(test_id, test_data)
        count += 1
    
    return count


def migrate_results():
    """Миграция результатов из JSON"""
    results_file = os.path.join(LOCAL_DATA_DIR, "results.json")
    if not os.path.exists(results_file):
        print("⚠️ results.json не найден, пропускаем")
        return 0
    
    with open(results_file, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return 0
        results = json.loads(content)
    
    count = 0
    for result in results:
        save_result(
            result["user_id"],
            result["test_id"],
            result["score"],
            result["total"],
            result.get("answers", [])
        )
        count += 1
    
    return count


if __name__ == "__main__":
    print("🚀 Начинаем миграцию данных в SQLite...\n")
    
    init_db()
    
    users_count = migrate_users()
    print(f"✅ Пользователей мигрировано: {users_count}")
    
    tests_count = migrate_tests()
    print(f"✅ Тестов мигрировано: {tests_count}")
    
    results_count = migrate_results()
    print(f"✅ Результатов мигрировано: {results_count}")
    
    print(f"\n📊 Итого мигрировано: {users_count + tests_count + results_count} записей")
    print("\nТеперь можно удалить старые JSON файлы:")
    print("  rm data/users.json data/tests.json data/results.json")
