# 🚀 Быстрая установка

## Шаг 1: Получить токен бота

1. Открыть [@BotFather](https://t.me/BotFather) в Telegram
2. Отправить команду `/newbot`
3. Придумать имя (например: "Моя книжная полка")
4. Придумать username (например: "my_bookshelf_bot")
5. Скопировать токен (выглядит как `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

## Шаг 2: Установить зависимости

### Windows
```bash
# Скачать Python 3.11+ с python.org, если ещё не установлен

# В папке проекта:
pip install -r requirements.txt
```

### Linux/Mac
```bash
# Установить Python 3.11+
sudo apt update && sudo apt install python3 python3-pip  # Ubuntu/Debian
brew install python3  # macOS

# В папке проекта:
pip3 install -r requirements.txt
```

## Шаг 3: Настроить .env

```bash
# Скопировать пример
copy .env.example .env      # Windows
cp .env.example .env        # Linux/Mac

# Открыть .env в текстовом редакторе и указать:
BOT_TOKEN=ваш_токен_от_BotFather
ADMIN_ID=ваш_telegram_id  # узнаете после первого запуска командой /id
```

## Шаг 4: Запустить

### Windows
```bash
start.bat
```

### Linux/Mac
```bash
chmod +x start.sh
./start.sh
```

Или напрямую:
```bash
python bot.py         # Windows
python3 bot.py        # Linux/Mac
```

## Шаг 5: Узнать свой ID

1. Открыть бота в Telegram
2. Отправить команду `/id`
3. Скопировать ID и добавить в `.env`:
   ```
   ADMIN_ID=123456789
   ```
4. Перезапустить бота

Готово! 🎉

## Дополнительно (опционально)

### Google Books API (для лучшего поиска)

1. Перейти на https://console.cloud.google.com/
2. Создать новый проект
3. Включить "Books API"
4. Создать API Key
5. Добавить в `.env`:
   ```
   GOOGLE_BOOKS_KEY=ваш_ключ
   ```

### Anthropic API (для AI-рекомендаций)

1. Зарегистрироваться на https://console.anthropic.com/
2. Создать API Key
3. Добавить в `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### Запуск как службы (Linux)

Создать файл `/etc/systemd/system/tomik.service`:

```ini
[Unit]
Description=Tomik Book Bot
After=network.target

[Service]
Type=simple
User=ваш_пользователь
WorkingDirectory=/путь/к/tomikru
ExecStart=/usr/bin/python3 /путь/к/tomikru/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tomik
sudo systemctl start tomik
sudo systemctl status tomik  # проверить статус
```

### Запуск в Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

Запуск:
```bash
docker build -t tomik .
docker run -d --name tomik --env-file .env --restart unless-stopped tomik
```

## Обновление

```bash
git pull
pip install -r requirements.txt  # на всякий случай
python bot.py  # или start.bat / start.sh
```

База данных обновится автоматически при запуске.

## Резервное копирование

База хранится в файле `tomik.db`. Автоматические резервные копии создаются в папке `backups/` каждый день в 04:00.

Вручную:
```bash
# Скопировать базу
copy tomik.db tomik-backup.db      # Windows
cp tomik.db tomik-backup.db        # Linux/Mac

# Или через бота (админу)
/backup
```

## Проблемы?

### Бот не запускается
- Проверьте, что токен указан правильно в `.env`
- Убедитесь, что установлены все зависимости
- Посмотрите логи ошибок

### Не работает поиск книг
- Добавьте `GOOGLE_BOOKS_KEY` в `.env` (см. выше)
- Проверьте интернет-соединение
- Попробуйте другой запрос

### Не работают картинки с итогами
- Убедитесь, что установлен `pillow`: `pip install pillow`
- Проверьте, что есть шрифты в системе
- Можно указать путь к шрифтам в `.env`

### Inline-режим не работает
- В настройках бота у @BotFather включите inline mode:
  ```
  /setinline
  [выбрать бота]
  Поиск книг...
  ```

---

Нужна помощь? [@fyave](https://t.me/fyave)
