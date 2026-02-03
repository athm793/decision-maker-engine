from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url

from app.core.settings import settings

SQLALCHEMY_DATABASE_URL = settings.database_url

connect_args: dict = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    try:
        url = make_url(SQLALCHEMY_DATABASE_URL)
        if (url.drivername or "").startswith("postgresql"):
            import socket

            host = url.host
            port = int(url.port or 5432)
            if host:
                infos = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
                if infos:
                    ipv4 = infos[0][4][0]
                    if ipv4:
                        connect_args = {"sslmode": "require", "hostaddr": ipv4}
    except Exception:
        connect_args = {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
