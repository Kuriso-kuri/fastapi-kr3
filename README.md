# FastAPI KR3 — Аутентификация и CRUD

## Установка и запуск

```bash
# 1. Создать виртуальное окружение
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Создать .env из примера
copy .env.example .env       # Windows
# cp .env.example .env       # Linux/Mac

# 4. Запустить
uvicorn main:app --reload
```

Приложение доступно по адресу: http://localhost:8000

## Переменные окружения (.env)

| Переменная    | Описание                        | По умолчанию |
|---------------|---------------------------------|--------------|
| MODE          | DEV или PROD                    | DEV          |
| DOCS_USER     | Логин для доступа к /docs       | admin        |
| DOCS_PASSWORD | Пароль для доступа к /docs      | admin        |

## Документация API

В режиме DEV: http://localhost:8000/docs (требует логин/пароль из .env)  
В режиме PROD: /docs возвращает 404

## Тестирование эндпоинтов (curl)

### 6.1 — GET /login (Basic Auth)
```bash
# Сначала зарегистрироваться через 6.2, затем:
curl -u user1:pass123 http://localhost:8000/login
```

### 6.2 — Регистрация
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"user1\", \"password\": \"pass123\"}"
```

### 6.4 — POST /login (JWT)
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"user1\", \"password\": \"pass123\"}"
```

### 6.4 — GET /protected_resource
```bash
curl http://localhost:8000/protected_resource \
  -H "Authorization: Bearer <токен из /login>"
```

### 7.1 — RBAC (назначить роль admin)
```bash
# Назначить роль (нужен токен admin-пользователя)
curl -X POST "http://localhost:8000/admin/promote?username=user1&role=admin" \
  -H "Authorization: Bearer <токен>"

# Доступ к admin-ресурсу
curl -X POST http://localhost:8000/admin/resource \
  -H "Authorization: Bearer <токен>"
```

### 8.1 — Регистрация в SQLite
```bash
curl -X POST http://localhost:8000/db/register \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"test_user\", \"password\": \"12345\"}"
```

### 8.2 — CRUD Todo
```bash
# Создать
curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"Buy groceries\", \"description\": \"Milk, eggs, bread\"}"

# Получить
curl http://localhost:8000/todos/1

# Обновить
curl -X PUT http://localhost:8000/todos/1 \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"Done\", \"description\": \"All bought\", \"completed\": true}"

# Удалить
curl -X DELETE http://localhost:8000/todos/1
```

## Роли пользователей (7.1)

| Роль  | Доступные действия        |
|-------|---------------------------|
| admin | create, read, update, delete |
| user  | read, update              |
| guest | read                      |

По умолчанию новый пользователь получает роль `user`.  
Сменить роль может только `admin` через `POST /admin/promote`.

Чтобы создать первого admin-а — зарегистрируйте пользователя и вручную измените роль в `fake_users_db` или используйте эндпоинт promote с токеном существующего admin.
