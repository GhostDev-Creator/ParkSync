# Arquivo: Back-End/database/setup_db.py
#
# ÚNICO lugar onde existem engine, Base e SessionLocal.
# Todos os outros arquivos importam daqui: from database.setup_db import ...

from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from utils import config

if config.DATABASE_URL:
    DB_URL = config.DATABASE_URL
else:
    DB_URL = (
        f"mysql+pymysql://{quote_plus(config.DB_USER)}:{quote_plus(config.DB_PASSWORD or '')}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}?charset=utf8mb4"
    )

_eh_sqlite = DB_URL.startswith("sqlite")

engine = create_engine(
    DB_URL,
    echo=False,
    pool_pre_ping=True,  # reconecta sozinho se o MySQL derrubar a conexão ociosa
    connect_args={"check_same_thread": False} if _eh_sqlite else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _criar_banco_mysql():
    """Cria o database no MySQL caso ainda não exista."""
    import pymysql

    conexao = pymysql.connect(
        host=config.DB_HOST, user=config.DB_USER, password=config.DB_PASSWORD or "", port=config.DB_PORT
    )
    try:
        with conexao.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conexao.commit()
    finally:
        conexao.close()


def init_db():
    """Cria o banco (MySQL) e todas as tabelas. Mostra erro claro se o MySQL estiver desligado."""
    import database.models  # noqa: F401  (registra as tabelas na Base)

    if not _eh_sqlite:
        try:
            _criar_banco_mysql()
        except Exception as e:
            raise RuntimeError(
                f"Não consegui conectar no MySQL em {config.DB_HOST}:{config.DB_PORT} "
                f"com o usuário '{config.DB_USER}'. Confira se o MySQL está ligado e os dados DB_* do .env. "
                f"Erro original: {e}"
            ) from e

    Base.metadata.create_all(bind=engine)
    print("🗄️  Banco de dados pronto.")
