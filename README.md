# FastAPI KR3

Контрольная работа №3 по дисциплине "Технологии разработки серверных приложений"

## Как запустить

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

Документация: http://localhost:8000/docs (логин/пароль из .env, по умолчанию admin/admin)

## Переменные окружения

Создать файл .env на основе .env.example:
- MODE - режим работы (DEV или PROD)
- DOCS_USER - логин для /docs
- DOCS_PASSWORD - пароль для /docs

В режиме PROD документация недоступна (404).

## Тестирование

Регистрация:
```
curl -X POST http://localhost:8000/register -H "Content-Type: application/json" -d "{\"username\": \"user1\", \"password\": \"pass123\"}"
```

Вход и получение токена:
```
curl -X POST http://localhost:8000/login -H "Content-Type: application/json" -d "{\"username\": \"user1\", \"password\": \"pass123\"}"
```

Защищённый ресурс:
```
curl http://localhost:8000/protected_resource -H "Authorization: Bearer <токен>"
```

По умолчанию создаётся пользователь admin с паролем admin123 и ролью admin.
