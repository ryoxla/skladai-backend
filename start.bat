@echo off
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
uvicorn main:app --reload --host 0.0.0.0 --port 8000
