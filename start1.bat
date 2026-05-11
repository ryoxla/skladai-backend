@echo off
chcp 65001 > nul
cd /d C:\Users\User\Documents\DOCS\Skladai\skladai_backend

echo === СкладAI Backend ===
echo.

REM Проверяем виртуальное окружение
if not exist "venv\Scripts\activate.bat" (
    echo Создаю виртуальное окружение...
    python -m venv venv
)

echo Активирую окружение...
call venv\Scripts\activate.bat

echo Устанавливаю зависимости...
pip install -r requirements.txt --quiet

echo.
echo Запускаю сервер...
echo Документация API: http://localhost:8000/docs
echo.

REM Запускаем FastAPI в отдельном окне
start "СкладAI Backend" cmd /k "chcp 65001 && cd /d C:\Users\User\Documents\DOCS\Skladai\skladai_backend && call venv\Scripts\activate.bat && uvicorn main:app --reload --host 0.0.0.0 --port 8000"

REM Ждём 3 секунды пока FastAPI запустится
timeout /t 3 /nobreak > nul

REM Запускаем ngrok в отдельном окне
start "ngrok туннель" cmd /k "cd /d C:\ngrok\ngrok.exe && .\ngrok http 8000"

echo.
echo FastAPI запущен на http://localhost:8000
echo ngrok запускается... смотри окно "ngrok туннель"
echo Там будет ссылка вида: https://abc123.ngrok-free.app
echo Эту ссылку отправляй пользователям!
echo.
pause
