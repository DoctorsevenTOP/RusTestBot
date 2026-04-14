#!/usr/bin/env python
"""
Тестовый скрипт для проверки работы тестов на вставку букв
Запустите после запуска бота для создания тестового теста
"""

import asyncio
import sqlite3
import json
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_manager

def create_sample_insert_test():
    """Создать демонстрационный тест на вставку букв"""
    
    print("=" * 60)
    print("СОЗДАНИЕ ДЕМОНСТРАЦИОННОГО ТЕСТА НА ВСТАВКУ БУКВ")
    print("=" * 60)
    
    # Проверяем базу данных
    if not os.path.exists(data_manager.DB_FILE):
        print(f"❌ База данных не найдена: {data_manager.DB_FILE}")
        print("Сначала запустите бота: python main.py")
        return False
    
    # Создаём тестовые вопросы
    questions = [
        {
            "type": "insert_letter",
            "text": "В комнате стоял див..н, который был украше.. узором.",
            "gaps": [
                {"position": 0, "correct": "а"},
                {"position": 1, "correct": "н"}
            ],
            "letters": ["а", "о", "н", "е"],
            "description": "Вставьте пропущенные буквы"
        },
        {
            "type": "insert_letter",
            "text": "Краше..ая корзина была поставле..а на стол.",
            "gaps": [
                {"position": 0, "correct": "нн"},
                {"position": 1, "correct": "а"}
            ],
            "letters": ["н", "нн", "а", "о"],
            "description": "Вставьте пропущенные буквы"
        },
        {
            "type": "insert_letter",
            "text": "М..чта озаряла к..мнату тёплым светом.",
            "gaps": [
                {"position": 0, "correct": "е"},
                {"position": 1, "correct": "о"}
            ],
            "letters": ["е", "и", "о", "а"],
            "description": "Вставьте пропущенные буквы"
        }
    ]
    
    # Создаём тест
    test_id = data_manager.generate_test_id()
    test_data = {
        "title": "Правописание согласных",
        "description": "Тест на вставку пропущенных букв в словах",
        "active": True,
        "questions": questions,
        "created_by": 0,  # Системный тест
        "created_at": data_manager.get_now_msk()
    }
    
    # Сохраняем
    try:
        data_manager.save_test(test_id, test_data)
        
        print(f"✅ Тест создан успешно!")
        print(f"\nID теста: {test_id}")
        print(f"Название: {test_data['title']}")
        print(f"Описание: {test_data['description']}")
        print(f"Вопросов: {len(questions)}")
        print(f"\n{'=' * 60}")
        print("ТЕПЕРЬ МОЖНО ПРОЙТИ ТЕСТ!")
        print("Нажмите кнопку '✍️ Вставка букв' в Telegram боте")
        print(f"{'=' * 60}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания теста: {e}")
        return False


def show_existing_tests():
    """Показать существующие тесты"""
    print("\n" + "=" * 60)
    print("СУЩЕСТВУЮЩИЕ ТЕСТЫ В БАЗЕ")
    print("=" * 60)
    
    tests = data_manager.get_tests()
    
    if not tests:
        print("❌ Нет тестов в базе данных")
        return
    
    for test_id, test in tests.items():
        insert_questions = [q for q in test.get("questions", []) if q.get("type") == "insert_letter"]
        
        print(f"\n📝 Тест #{test_id}")
        print(f"   Название: {test['title']}")
        print(f"   Активен: {'✅' if test.get('active', True) else '❌'}")
        print(f"   Вопросов на вставку: {len(insert_questions)}")
        print(f"   Всего вопросов: {len(test.get('questions', []))}")


if __name__ == "__main__":
    print()
    
    # Показываем существующие тесты
    show_existing_tests()
    
    print()
    
    # Спрашиваем создать новый тест
    response = input("Создать демонстрационный тест? (д/н): ").strip().lower()
    
    if response == 'д' or response == 'y' or response == '':
        create_sample_insert_test()
    else:
        print("Отмена создания теста")
    
    print()
