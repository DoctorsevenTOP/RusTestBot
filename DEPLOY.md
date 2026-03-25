# Инструкция по запуску бота на сервере

## 1. Подготовка

```bash
# Подключитесь к серверу
ssh user@your-server.com

# Перейдите в директорию бота
cd /path/to/TgRusCheck

# Установите зависимости (если ещё не установлены)
pip install -r requirements.txt
```

## 2. Настройка

```bash
# Отредактируйте config.py
nano config.py

# Введите ваш токен от BotFather
# Убедитесь что ADMIN_IDS содержит ваш Telegram ID
```

## 3. Запуск

### Вариант A: Прямой запуск (рекомендуется для тестирования)

```bash
# Запустите бота
python main.py

# Для работы в фоне используйте nohup или screen:
nohup python main.py > bot.log 2>&1 &

# Или через screen:
screen -S bot
python main.py
# Ctrl+A, D для открепления
```

### Вариант B: Через systemd (для production)

```bash
# Создайте сервис
sudo nano /etc/systemd/system/tg-ruscheck.service
```

Содержимое файла:
```ini
[Unit]
Description=Telegram Russian Test Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/TgRusCheck
ExecStart=/usr/bin/python3 /path/to/TgRusCheck/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Перезапустите systemd и запустите сервис
sudo systemctl daemon-reload
sudo systemctl enable tg-ruscheck
sudo systemctl start tg-ruscheck

# Проверка статуса
sudo systemctl status tg-ruscheck

# Просмотр логов
sudo journalctl -u tg-ruscheck -f
```

## 4. Настройка администратора

```bash
# Запустите скрипт назначения администратора
python set_admin.py 5153839634

# Проверьте базу данных
python -c "from data_manager import get_user; print(get_user(5153839634))"

# Должно вывести: {'admin': 1, ...}
```

## 5. Проверка работы

1. Отправьте боту `/start`
2. Отправьте `/me` — должно показать "Администратор: ✅ Да"
3. Отправьте `/ping` — покажет информацию о сервере

## 6. Отладка

### Просмотр логов при запуске:
```bash
python main.py 2>&1 | tee bot.log
```

### Проверка базы данных:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/bot.db')
cursor = conn.cursor()
cursor.execute('SELECT telegram_id, name, admin FROM users')
for row in cursor.fetchall():
    print(row)
conn.close()
"
```

### Проверка прав доступа:
```bash
ls -la data/
chmod 755 data/
```

## 7. Частые проблемы

### Бот не сохраняет данные:
1. Проверьте права на папку `data/`: `ls -la data/`
2. Проверьте путь в логах при старте
3. Убедитесь что `data_manager.py` использует абсолютный путь

### Администратор не работает:
1. Проверьте базу: `python set_admin.py <ваш_id>`
2. Проверьте через `/me` в Telegram
3. Перезапустите бота после назначения

### Ошибки при старте:
1. Проверьте токен в `config.py`
2. Установите все зависимости: `pip install -r requirements.txt`
3. Смотрите логи ошибки

## 8. Остановка бота

```bash
# Если запущен в фоне через nohup
pkill -f "python main.py"

# Если через systemd
sudo systemctl stop tg-ruscheck
```
