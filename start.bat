@echo off
echo ========================================
echo   📚 Томик - Книжный бот для Telegram
echo ========================================
echo.

if not exist ".env" (
    echo ❌ Ошибка: файл .env не найден!
    echo.
    echo Создайте файл .env на основе .env.example:
    echo   copy .env.example .env
    echo.
    echo И укажите BOT_TOKEN от @BotFather
    echo.
    pause
    exit /b 1
)

echo ✅ Проверка зависимостей...
python -c "import aiogram, aiohttp, PIL, zxingcpp" 2>nul
if errorlevel 1 (
    echo.
    echo ⚠️  Не все зависимости установлены.
    echo Устанавливаю...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ❌ Ошибка установки зависимостей
        pause
        exit /b 1
    )
)

echo.
echo ✅ Зависимости готовы
echo.
echo 🚀 Запуск бота...
echo.
echo Для остановки нажмите Ctrl+C
echo.
echo ========================================
echo.

python bot.py

if errorlevel 1 (
    echo.
    echo ❌ Бот завершился с ошибкой
    pause
    exit /b 1
)
