"""Moteur et session SQLite pour Marque-page.

La base vit dans /app/data (volume Docker du MN56), en mode WAL.
Le chemin peut être surchargé via MARQUEPAGE_DB pour les tests ou une
exécution hors conteneur.
"""

import os
import unicodedata

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

# URL par défaut : volume Docker /app/data. Surchargable pour tests.
DATABASE_URL = os.environ.get("MARQUEPAGE_DB", "sqlite:////app/data/marquepage.db")

# check_same_thread=False : le moteur est partagé entre requêtes FastAPI.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def unaccent(text: str) -> str:
    """Normalisation de recherche : minuscules + accents ôtés.

    « Déjà vu » -> « deja vu ». Enregistrée comme fonction SQLite
    (`unaccent`) pour rendre la recherche insensible à la casse ET aux
    accents — le LIKE natif de SQLite ne plie que l'ASCII, ce qui rate
    « POÈTES » face à « poètes ».
    """
    if not text:
        return ""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if not unicodedata.combining(c)).lower()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """WAL + intégrité référentielle à chaque connexion.

    WAL est persistant dans le fichier de base, mais le réaffirmer à chaque
    connexion est gratuit et robuste. foreign_keys est par contre un pragma
    de connexion : sans lui, les `ON DELETE CASCADE` du schéma sont ignorés.
    La fonction `unaccent` est enregistrée ici aussi : c'est une fonction
    SQLite *par connexion*.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
    dbapi_connection.create_function("unaccent", 1, unaccent)


def get_session():
    """Dépendance FastAPI — session par requête."""
    with Session(engine) as session:
        yield session
