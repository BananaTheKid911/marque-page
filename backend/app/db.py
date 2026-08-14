"""Moteur et session SQLite pour Marque-page.

La base vit dans /app/data (volume Docker du MN56), en mode WAL.
Le chemin peut être surchargé via MARQUEPAGE_DB pour les tests ou une
exécution hors conteneur.
"""

import os

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

# URL par défaut : volume Docker /app/data. Surchargable pour tests.
DATABASE_URL = os.environ.get("MARQUEPAGE_DB", "sqlite:////app/data/marquepage.db")

# check_same_thread=False : le moteur est partagé entre requêtes FastAPI.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """WAL + intégrité référentielle à chaque connexion.

    WAL est persistant dans le fichier de base, mais le réaffirmer à chaque
    connexion est gratuit et robuste. foreign_keys est par contre un pragma
    de connexion : sans lui, les `ON DELETE CASCADE` du schéma sont ignorés.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session():
    """Dépendance FastAPI — session par requête."""
    with Session(engine) as session:
        yield session
