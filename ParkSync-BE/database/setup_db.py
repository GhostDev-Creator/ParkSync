import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
import pymysql
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
db_host = os.getenv("DB_HOST")
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_port = os.getenv("DB_PORT")

conection_server = pymysql.connect(
    host=db_host, user=db_user, password=db_pass, port=int(db_port)
)

try:
    with conection_server.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name};")
    conection_server.commit()
finally:
    conection_server.close()

DB_URL = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    Base.metadata.create_all(engine)