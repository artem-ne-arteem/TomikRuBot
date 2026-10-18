#!/bin/bash

echo "========================================"
echo "  📚 Томик - Книжный бот для Telegram"
echo "========================================"
echo ""

if [ ! -f ".env" ]; then
    echo "❌ Ошибка: файл .env не найден!"
    echo ""
    echo "Создайте файл .env на основе .env.example:"
    echo "  cp .env.example .env"
    echo ""
    echo "И укажите BOT_TOKEN от @BotFather"
    echo ""
    exit 1
fi

echo "✅ Проверка зависимостей..."
python3 -c "import aiogram, aiohttp, PIL, zxingcpp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  Не все зависимости установлены."
    echo "Устанавливаю..."
    echo ""
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Ошибка установки зависимостей"
        exit 1
    fi
fi

echo ""
echo "✅ Зависимости готовы"
echo ""
echo "🚀 Запуск бота..."
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""
echo "========================================"
echo ""

python3 bot.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Бот завершился с ошибкой"
    exit 1
fi
