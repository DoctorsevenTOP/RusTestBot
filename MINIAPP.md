# Инструкция по развёртыванию Mini App

## 1. Хостинг для Mini App

Telegram Mini App требует HTTPS. Вот бесплатные варианты:

### Вариант A: GitHub Pages (рекомендуется)

1. Создайте репозиторий на GitHub
2. Загрузите `miniapp.html` в корень репозитория
3. Переименуйте в `index.html`
4. Включите GitHub Pages в настройках репозитория
5. Получите URL: `https://yourusername.github.io/repo-name/`

### Вариант B: Vercel / Netlify

1. Зарегистрируйтесь на vercel.com или netlify.com
2. Загрузите файл `miniapp.html`
3. Получите HTTPS URL

### Вариант C: Ваш сервер

Если у вас есть сервер с nginx:

```bash
# Скопируйте файл на сервер
scp miniapp.html user@server:/var/www/miniapp/

# Настройте nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    root /var/www/miniapp;
    index miniapp.html;
}
```

## 2. Обновление URL в боте

Откройте `main.py` и найдите строку:

```python
app_url = f"https://your-domain.com/miniapp.html?data={quote(json.dumps(app_data))}"
```

Замените `https://your-domain.com/miniapp.html` на ваш URL:

```python
app_url = f"https://yourusername.github.io/repo-name/index.html?data={quote(json.dumps(app_data))}"
```

## 3. Создание задания на вставку букв

### Через test_builder.html:

1. Откройте `test_builder.html` в браузере
2. Перейдите на вкладку "✍️ Вставка букв"
3. Введите название задания
4. Введите текст с пропусками (используйте `..` для пропуска)
   - Пример: `В комнате стоял див..н, который был украше.. узором.`
5. Укажите правильные буквы для каждого пропуска
6. Добавьте варианты букв для выбора (минимум 2)
7. Нажмите "➕ Добавить задание в тест"
8. Скопируйте JSON

### Пример JSON:

```json
{
  "type": "insert_letter",
  "description": "Вставьте пропущенные буквы",
  "text": "В комнате стоял див___н, который был украше___ узором.",
  "gaps": [
    {"index": 22, "correct": "а", "length": 1},
    {"index": 44, "correct": "н", "length": 1}
  ],
  "letters": ["а", "о", "н", "нн", "е"]
}
```

### Добавление в тест:

Создайте полный тест с вопросом:

```json
{
  "title": "Правописание -Н- и -НН-",
  "description": "Тест на правописание",
  "active": true,
  "questions": [
    {
      "type": "insert_letter",
      "description": "Вставьте пропущенные буквы",
      "text": "В комнате стоял див___н, который был украше___ узором.",
      "gaps": [
        {"index": 22, "correct": "а"},
        {"index": 44, "correct": "н"}
      ],
      "letters": ["а", "о", "н", "нн", "е"]
    }
  ]
}
```

Отправьте JSON боту через `/load_test`.

## 4. Использование

1. Пользователь отправляет `/insert`
2. Бот показывает список доступных заданий
3. Пользователь выбирает задание
4. Открывается Mini App
5. Пользователь нажимает на пропуски и выбирает буквы
6. Нажимает "Проверить ответы"
7. Нажимает "Отправить результат"
8. Результат сохраняется в таблице лидеров

## 5. Тестирование

Для быстрого тестирования без развёртывания:

1. Используйте ngrok для локального хостинга:
```bash
ngrok http 8000
```

2. Откройте `miniapp.html` локально:
```bash
python -m http.server 8000
```

3. Используйте URL от ngrok в боте

## 6. Настройка Telegram Web App

В @BotFather:

1. Выберите вашего бота
2. Bot Settings → Menu Button → Configure Menu Button
3. Отправьте URL вашего Mini App
4. Укажите название кнопки

Или используйте команду `/newapp` в @BotFather для создания отдельного Web App.
