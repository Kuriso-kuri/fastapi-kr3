import os
import secrets
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasicCredentials
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from auth import (
    auth_user,
    create_access_token,
    fake_users_db,
    get_current_user,
    hash_password,
    require_role,
    security_basic,
    verify_password,
)
from database import get_db_connection, init_db
from models import (
    LoginRequest,
    TodoCreate,
    TodoResponse,
    TodoUpdate,
    User,
    UserInDB,
)

load_dotenv()

MODE = os.getenv("MODE", "DEV").upper()
DOCS_USER = os.getenv("DOCS_USER", "admin")
DOCS_PASSWORD = os.getenv("DOCS_PASSWORD", "admin")

if MODE not in ("DEV", "PROD"):
    raise ValueError(f"Недопустимое значение MODE: {MODE!r}. Допустимые: DEV, PROD")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from auth import init_default_users
    init_default_users()
    yield


app = FastAPI(
    title="FastAPI KR3",
    description="Система аутентификации и управления задачами",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Аутентификация",
            "description": "Вход в систему и регистрация пользователей",
        },
        {
            "name": "Защищённые ресурсы",
            "description": "Доступ только с JWT-токеном",
        },
        {
            "name": "Управление ролями",
            "description": "Эндпоинты с ограничением по ролям: admin, user, guest",
        },
        {
            "name": "База данных",
            "description": "Регистрация пользователей через SQLite (задание 8.1)",
        },
        {
            "name": "Задачи",
            "description": "Создание, чтение, обновление и удаление задач (Todo)",
        },
    ],
)

# Rate limiter (задание 6.5)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


# Задание 6.3: защита /docs в DEV, скрытие в PROD
def check_docs_auth(credentials: HTTPBasicCredentials = Security(security_basic)):
    ok_user = secrets.compare_digest(credentials.username, DOCS_USER)
    ok_pass = secrets.compare_digest(credentials.password, DOCS_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": "Basic"},
            detail="Unauthorized",
        )
    return credentials


if MODE == "DEV":
    @app.get("/docs", include_in_schema=False)
    async def get_docs(credentials=Depends(check_docs_auth)):
        return get_swagger_ui_html(openapi_url="/openapi.json", title="Docs")

    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_json(credentials=Depends(check_docs_auth)):
        return get_openapi(title=app.title, version="1.0.0", routes=app.routes)

else:
    @app.get("/docs", include_in_schema=False)
    async def docs_disabled():
        raise HTTPException(status_code=404)

    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_disabled():
        raise HTTPException(status_code=404)

    @app.get("/redoc", include_in_schema=False)
    async def redoc_disabled():
        raise HTTPException(status_code=404)


# ───────────────────────────────────────────────
# Задание 6.1 — GET /login с базовой аутентификацией
# ───────────────────────────────────────────────
@app.get(
    "/login",
    tags=["Аутентификация"],
    summary="Вход через Basic Auth",
    description="Проверяет логин и пароль через HTTP Basic Auth. Возвращает приветствие.",
)
async def login_basic(current_user=Depends(auth_user)):
    return {"message": f"Welcome, {current_user.username}!"}


# ───────────────────────────────────────────────
# Задание 6.2 — POST /register с хешированием
# ───────────────────────────────────────────────
@app.post(
    "/register",
    tags=["Аутентификация"],
    summary="Регистрация нового пользователя",
    description="Создаёт пользователя с хешированным паролем (bcrypt). Лимит: 1 запрос в минуту.",
)
@limiter.limit("1/minute")
async def register(request: Request, user: User):
    for db_username in fake_users_db:
        if secrets.compare_digest(db_username, user.username):
            raise HTTPException(status_code=409, detail="User already exists")

    hashed = hash_password(user.password)
    fake_users_db[user.username] = UserInDB(
        username=user.username,
        hashed_password=hashed,
        role="user",
    )
    return {"message": f"User '{user.username}' successfully added"}


# ───────────────────────────────────────────────
# Задание 6.4 — POST /login с JWT
# ───────────────────────────────────────────────
@app.post(
    "/login",
    tags=["Аутентификация"],
    summary="Вход и получение JWT-токена",
    description="Проверяет логин и пароль, возвращает JWT access_token. Лимит: 5 запросов в минуту.",
)
@limiter.limit("5/minute")
async def login_jwt(request: Request, body: LoginRequest):
    found_user = None
    for db_username, user in fake_users_db.items():
        if secrets.compare_digest(db_username, body.username):
            found_user = user
            break

    if found_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.password, found_user.hashed_password):
        raise HTTPException(status_code=401, detail="Authorization failed")

    token = create_access_token({"sub": found_user.username})
    return {"access_token": token, "token_type": "bearer"}


# ───────────────────────────────────────────────
# Задание 6.4 — GET /protected_resource (JWT)
# ───────────────────────────────────────────────
@app.get(
    "/protected_resource",
    tags=["Защищённые ресурсы"],
    summary="Защищённый ресурс (только с токеном)",
    description="Доступен только авторизованным пользователям. Передайте JWT-токен в заголовке Authorization: Bearer <токен>.",
)
async def protected_resource(current_user=Depends(get_current_user)):
    return {"message": "Access granted"}


# ───────────────────────────────────────────────
# Задание 7.1 — RBAC эндпоинты
# ───────────────────────────────────────────────
ROLES = {
    "admin": ["create", "read", "update", "delete"],
    "user":  ["read", "update"],
    "guest": ["read"],
}


@app.post(
    "/admin/resource",
    tags=["Управление ролями"],
    summary="Создать ресурс (только admin)",
    dependencies=[Depends(require_role("admin"))],
)
async def admin_create():
    return {"message": "Ресурс создан (только для admin)"}


@app.get(
    "/user/resource",
    tags=["Управление ролями"],
    summary="Прочитать ресурс (admin и user)",
    dependencies=[Depends(require_role("admin", "user"))],
)
async def user_read():
    return {"message": "Ресурс прочитан (admin и user)"}


@app.put(
    "/user/resource",
    tags=["Управление ролями"],
    summary="Обновить ресурс (admin и user)",
    dependencies=[Depends(require_role("admin", "user"))],
)
async def user_update():
    return {"message": "Ресурс обновлён (admin и user)"}


@app.delete(
    "/admin/resource",
    tags=["Управление ролями"],
    summary="Удалить ресурс (только admin)",
    dependencies=[Depends(require_role("admin"))],
)
async def admin_delete():
    return {"message": "Ресурс удалён (только для admin)"}


@app.get(
    "/guest/resource",
    tags=["Управление ролями"],
    summary="Публичный ресурс (все роли)",
    dependencies=[Depends(require_role("admin", "user", "guest"))],
)
async def guest_read():
    return {"message": "Публичный ресурс (все роли)"}


@app.post(
    "/admin/promote",
    tags=["Управление ролями"],
    summary="Назначить роль пользователю (только admin)",
    description="Позволяет администратору изменить роль любого пользователя. Доступные роли: admin, user, guest.",
)
async def promote_user(username: str, role: str, current_user=Depends(require_role("admin"))):
    if role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Недопустимая роль. Допустимые: {list(ROLES)}")
    if username not in fake_users_db:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    fake_users_db[username].role = role
    return {"message": f"Роль пользователя '{username}' изменена на '{role}'"}


# ───────────────────────────────────────────────
# Задание 8.1 — POST /register в SQLite
# ───────────────────────────────────────────────
@app.post(
    "/db/register",
    tags=["База данных"],
    summary="Зарегистрировать пользователя в SQLite",
    description="Сохраняет имя пользователя и пароль в таблицу users базы данных SQLite.",
)
async def register_db(user: User):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        (user.username, user.password),
    )
    conn.commit()
    conn.close()
    return {"message": "User registered successfully!"}


# ───────────────────────────────────────────────
# Задание 8.2 — CRUD для Todo
# ───────────────────────────────────────────────
@app.post(
    "/todos",
    response_model=TodoResponse,
    status_code=201,
    tags=["Задачи"],
    summary="Создать новую задачу",
)
async def create_todo(todo: TodoCreate):
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO todos (title, description, completed) VALUES (?, ?, 0)",
        (todo.title, todo.description),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return TodoResponse(id=row["id"], title=row["title"], description=row["description"], completed=bool(row["completed"]))


@app.get(
    "/todos/{todo_id}",
    response_model=TodoResponse,
    tags=["Задачи"],
    summary="Получить задачу по ID",
)
async def get_todo(todo_id: int):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return TodoResponse(id=row["id"], title=row["title"], description=row["description"], completed=bool(row["completed"]))


@app.put(
    "/todos/{todo_id}",
    response_model=TodoResponse,
    tags=["Задачи"],
    summary="Обновить задачу по ID",
)
async def update_todo(todo_id: int, todo: TodoUpdate):
    conn = get_db_connection()
    result = conn.execute(
        "UPDATE todos SET title = ?, description = ?, completed = ? WHERE id = ?",
        (todo.title, todo.description, int(todo.completed), todo_id),
    )
    conn.commit()
    if result.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Todo not found")
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()
    return TodoResponse(id=row["id"], title=row["title"], description=row["description"], completed=bool(row["completed"]))


@app.delete(
    "/todos/{todo_id}",
    tags=["Задачи"],
    summary="Удалить задачу по ID",
)
async def delete_todo(todo_id: int):
    conn = get_db_connection()
    result = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"message": f"Todo {todo_id} удалена успешно"}
