FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаём директорию /data для постоянного хранилища
# Это важно для persistence mount
RUN mkdir -p /data && chmod 777 /data

# Переменная окружения для пути к данным
ENV DATA_DIR=/data

# Запускаем бота
CMD ["python", "main.py"]
