import secrets
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBasicCredentials, HTTPBasic, HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = "super-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_basic = HTTPBasic()
security_bearer = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# In-memory база пользователей.
# Дефолтный admin: логин=admin, пароль=admin123
# Хеш сгенерирован заранее чтобы не импортировать модели здесь
fake_users_db: dict = {}


def init_default_users():
    from models import UserInDB
    fake_users_db["admin"] = UserInDB(
        username="admin",
        hashed_password=hash_password("admin123"),
        role="admin",
    )


def auth_user(credentials: HTTPBasicCredentials = Security(security_basic)):
    from models import UserInDB

    username = credentials.username
    password = credentials.password

    found_user = None
    for db_username, user in fake_users_db.items():
        if secrets.compare_digest(db_username, username):
            found_user = user
            break

    if found_user is None or not verify_password(password, found_user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return found_user


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_bearer)):
    payload = decode_access_token(credentials.credentials)
    username = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    if username not in fake_users_db:
        raise HTTPException(status_code=401, detail="User not found")

    return fake_users_db[username]


def require_role(*roles: str):
    def dependency(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return dependency
