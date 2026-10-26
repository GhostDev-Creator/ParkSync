# Arquivo: Back-End/utils/security.py
#
# Senhas com bcrypt e token JWT de 1 semana.
# Usa a biblioteca bcrypt direto (o passlib está abandonado e quebra com bcrypt 4.1+).

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from utils import config

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = config.JWT_EXPIRA_MINUTOS  # 1 semana por padrão

if config.JWT_SECRET:
    SECRET_KEY = config.JWT_SECRET
else:
    # Não derruba a API, mas os tokens deixam de valer quando o servidor reinicia.
    SECRET_KEY = secrets.token_urlsafe(48)
    print("⚠️  JWT_SECRET não definida no .env: gerei uma chave temporária "
          "(o app terá que logar de novo sempre que a API reiniciar).")

_bearer = HTTPBearer(auto_error=False)


# ================= SENHAS =================
def _bytes_senha(senha: str) -> bytes:
    # O bcrypt só considera 72 bytes; cortamos para não dar erro com senhas longas.
    return senha.encode("utf-8")[:72]


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_bytes_senha(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_bytes_senha(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        return False


# ================= TOKEN JWT =================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Gera o token do app do morador. Sem expires_delta, vale 1 semana."""
    to_encode = data.copy()
    expira = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expira
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada. Faça login novamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")


def morador_do_token(credenciais: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> Optional[int]:
    """
    Dependência das rotas do morador. Devolve o id do morador do token.
    - Com token: sempre valida (expirado/inválido -> 401).
    - Sem token: só passa se EXIGIR_TOKEN=false no .env (compatível com o app atual).
    """
    if credenciais is None:
        if config.EXIGIR_TOKEN:
            raise HTTPException(status_code=401, detail="Faça login para continuar.")
        return None
    dados = decodificar_token(credenciais.credentials)
    try:
        return int(dados.get("id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido.")


def garantir_dono(morador_token: Optional[int], morador_id: int):
    """Impede o morador A de mexer nos dados do morador B."""
    if morador_token is not None and morador_token != morador_id:
        raise HTTPException(status_code=403, detail="Acesso negado a dados de outro morador.")


def exigir_portaria(request: Request, x_portaria_key: Optional[str] = Header(default=None)):
    """
    Rotas da portaria (abrir cancela manual, simular sensor, mapear vagas, trigger interno).
    Se PORTARIA_API_KEY estiver no .env, exige o header X-Portaria-Key.
    Se não estiver, só aceita chamadas do próprio computador (127.0.0.1).
    """
    if config.PORTARIA_API_KEY:
        if x_portaria_key != config.PORTARIA_API_KEY:
            raise HTTPException(status_code=401, detail="Chave da portaria inválida.")
        return
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(status_code=403, detail="Rota permitida só no computador da portaria.")
