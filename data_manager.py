"""Модуль для работы с данными (пользователи, тесты, результаты)"""
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import config


def ensure_data_dir():
    """Создать директорию для данных если не существует"""
    os.makedirs("data", exist_ok=True)


def load_json(filepath: str) -> Any:
    """Загрузить данные из JSON файла"""
    ensure_data_dir()
    if not os.path.exists(filepath):
        return {} if "users" in filepath or "tests" in filepath else []
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:  # Пустой файл
            return {} if "users" in filepath or "tests" in filepath else []
        return json.loads(content)


def save_json(filepath: str, data: Any):
    """Сохранить данные в JSON файл"""
    ensure_data_dir()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# === Пользователи ===
def get_users() -> Dict[str, Dict]:
    """Получить всех пользователей"""
    return load_json(config.USERS_FILE)


def is_name_taken(name: str) -> bool:
    """Проверить, занято ли имя"""
    users = get_users()
    name_lower = name.lower().strip()
    for user in users.values():
        if user.get("name", "").lower().strip() == name_lower:
            return True
    return False


def get_user_by_name(name: str) -> Optional[Dict]:
    """Получить пользователя по имени"""
    users = get_users()
    name_lower = name.lower().strip()
    for user in users.values():
        if user.get("name", "").lower().strip() == name_lower:
            return user
    return None


def save_user(user_id: int, name: str):
    """Сохранить или обновить пользователя"""
    users = get_users()
    user_data = users.get(str(user_id), {})
    
    users[str(user_id)] = {
        "name": name,
        "telegram_id": user_id,
        "registered_at": datetime.now().isoformat(),
        "admin": user_data.get("admin", False)  # Сохраняем статус администратора
    }
    save_json(config.USERS_FILE, users)


def get_user(user_id: int) -> Optional[Dict]:
    """Получить пользователя по ID"""
    users = get_users()
    return users.get(str(user_id))


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    users = get_users()
    user = users.get(str(user_id))
    if user:
        return user.get("admin", False)
    # Fallback: проверяем ADMIN_IDS из config (для обратной совместимости)
    return user_id in config.ADMIN_IDS


def set_admin_status(user_id: int, admin: bool) -> bool:
    """Установить статус администратора для пользователя"""
    users = get_users()
    if str(user_id) not in users:
        return False
    
    users[str(user_id)]["admin"] = admin
    users[str(user_id)]["admin_updated_at"] = datetime.now().isoformat()
    save_json(config.USERS_FILE, users)
    return True


def get_all_admins() -> List[Dict]:
    """Получить всех администраторов"""
    users = get_users()
    return [
        {"user_id": int(uid), **data}
        for uid, data in users.items()
        if data.get("admin", False)
    ]


# === Тесты ===
def get_tests(only_active: bool = False) -> Dict[str, Dict]:
    """Получить все тесты (опционально только активные)"""
    tests = load_json(config.TESTS_FILE)
    if only_active:
        return {tid: t for tid, t in tests.items() if t.get("active", True)}
    return tests


def save_test(test_id: str, test_data: Dict):
    """Сохранить тест"""
    tests = get_tests()
    # По умолчанию тест активен
    if "active" not in test_data:
        test_data["active"] = True
    tests[test_id] = test_data
    save_json(config.TESTS_FILE, tests)


def get_test(test_id: str) -> Optional[Dict]:
    """Получить тест по ID"""
    tests = get_tests()
    return tests.get(test_id)


def toggle_test_active(test_id: str) -> Optional[bool]:
    """Переключить статус активности теста. Возвращает новый статус или None если тест не найден"""
    tests = get_tests()
    if test_id not in tests:
        return None
    
    current_status = tests[test_id].get("active", True)
    tests[test_id]["active"] = not current_status
    tests[test_id]["updated_at"] = datetime.now().isoformat()
    save_json(config.TESTS_FILE, tests)
    return not current_status


def set_test_active(test_id: str, active: bool) -> bool:
    """Установить статус активности теста. Возвращает True если успешно"""
    tests = get_tests()
    if test_id not in tests:
        return False
    
    tests[test_id]["active"] = active
    tests[test_id]["updated_at"] = datetime.now().isoformat()
    save_json(config.TESTS_FILE, tests)
    return True


def delete_test(test_id: str):
    """Удалить тест"""
    tests = get_tests()
    if test_id in tests:
        del tests[test_id]
        save_json(config.TESTS_FILE, tests)
        return True
    return False


def generate_test_id() -> str:
    """Сгенерировать уникальный ID для теста"""
    tests = get_tests()
    test_id = str(len(tests) + 1)
    while test_id in tests:
        test_id = str(int(test_id) + 1)
    return test_id


# === Результаты ===
def get_results() -> List[Dict]:
    """Получить все результаты"""
    return load_json(config.RESULTS_FILE)


def save_result(user_id: int, test_id: str, score: int, total: int, answers: List[Dict]):
    """Сохранить результат теста"""
    results = get_results()
    result = {
        "user_id": user_id,
        "test_id": test_id,
        "score": score,
        "total": total,
        "percentage": round(score / total * 100, 1) if total > 0 else 0,
        "answers": answers,
        "completed_at": datetime.now().isoformat()
    }
    results.append(result)
    save_json(config.RESULTS_FILE, results)
    return result


def get_test_results(test_id: str) -> List[Dict]:
    """Получить результаты конкретного теста"""
    results = get_results()
    return [r for r in results if r["test_id"] == test_id]


def get_user_results(user_id: int) -> List[Dict]:
    """Получить результаты пользователя"""
    results = get_results()
    return [r for r in results if r["user_id"] == user_id]


def get_leaderboard(test_id: str, limit: int = 10) -> List[Dict]:
    """Получить таблицу лидеров для теста (группировка по имени, лучший результат)"""
    results = get_test_results(test_id)
    
    if not results:
        return []
    
    # Группируем по user_id, берём лучший результат
    user_best_results = {}
    for r in results:
        uid = r["user_id"]
        if uid not in user_best_results or r["percentage"] > user_best_results[uid]["percentage"]:
            user_best_results[uid] = r
    
    # Сортируем по проценту правильных ответов (убывание)
    sorted_results = sorted(user_best_results.values(), key=lambda x: x["percentage"], reverse=True)

    leaderboard = []
    for r in sorted_results[:limit]:
        user = get_user(r["user_id"])
        leaderboard.append({
            "name": user["name"] if user else "Неизвестный",
            "score": r["score"],
            "total": r["total"],
            "percentage": r["percentage"],
            "date": r["completed_at"][:10],  # Дата
            "time": r["completed_at"][11:19],  # Время
            "completed_at": r["completed_at"]  # Полная дата и время
        })
    return leaderboard
