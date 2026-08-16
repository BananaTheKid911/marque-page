"""Tests de migration Alembic — upgrade/downgrade sur base scratch.

Le cycle est vérifié par exécution réelle sur un SQLite jetable (même
méthode que la vérification de ff98b093454f) :
1. upgrade jusqu'au head précédent (1d5d73910b32), le schéma d'avant ;
2. insertion de données réalistes en SQL brut — dont un livre avec l'ancien
   statut `wishlist` et des tables filles (la recreate batch ne doit rien
   emporter via les ON DELETE CASCADE) ;
3. upgrade vers la migration cible (7e869700ed63) : les colonnes sont là,
   le backfill est correct, le CHECK `ck_book_type` est actif ;
4. downgrade puis re-upgrade : cycle propre (marché arrière exact puis
   retour, aucune donnée perdue).

Les données sont insérées en SQL brut : à l'étape 1 le schéma est celui
d'avant le changement, les modèles SQLModel (qui portent maintenant les
nouvelles colonnes) ne correspondent pas encore.

Piège d'env.py : il surcharge l'URL de la Config avec `app.db.DATABASE_URL`
(lu dans MARQUEPAGE_DB par le conftest). Comme le script est ré-exécuté à
chaque commande alembic, on patche la valeur module avant chaque appel pour
forcer la base scratch — jamais celle du conftest.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import app.db

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

PREV_HEAD = "1d5d73910b32"
TARGET = "7e869700ed63"


def _config(db_path: Path) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _upgrade(cfg: Config, db_path: Path, rev: str) -> None:
    app.db.DATABASE_URL = f"sqlite:///{db_path}"  # ré-écrit au re-exec d'env.py
    command.upgrade(cfg, rev)


def _downgrade(cfg: Config, db_path: Path, rev: str) -> None:
    app.db.DATABASE_URL = f"sqlite:///{db_path}"
    command.downgrade(cfg, rev)


def _upgrade_to_previous(cfg: Config, db_path: Path) -> None:
    """Schéma d'avant + données réalistes (livre wishlist à l'ancienne,
    livre lu avec session et highlight, livre en pile)."""
    _upgrade(cfg, db_path, PREV_HEAD)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO book (id, title, status, owned, created_at, updated_at) VALUES "
            "(1, 'Souhait', 'wishlist', 0, '2026-01-01T00:00:00', '2026-01-01T00:00:00'),"
            "(2, 'Pile', 'tbr', 1, '2026-01-01T00:00:00', '2026-01-01T00:00:00'),"
            "(3, 'Lu', 'read', 1, '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO reading_session (id, book_id, started_at, duration_sec,"
            " source, created_at) VALUES (1, 3, '2026-01-02T10:00:00', 1800,"
            " 'manual', '2026-01-02T10:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO highlight (id, book_id, text, source, created_at)"
            " VALUES (1, 3, 'citation test', 'manual', '2026-01-02T10:00:00')"
        ))
    engine.dispose()


def _query(db_path: Path, sql: str) -> list:
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    engine.dispose()
    return rows


def test_upgrade_backfills_wishlist_and_adds_type(tmp_path):
    db_path = tmp_path / "m.db"
    cfg = _config(db_path)
    _upgrade_to_previous(cfg, db_path)

    _upgrade(cfg, db_path, TARGET)

    rows = _query(db_path, "SELECT id, status, is_wishlist, type FROM book ORDER BY id")
    # backfill : l'ancien wishlist porte is_wishlist=1 et un status valide
    assert rows[0] == (1, "tbr", 1, "livre")
    # les autres : flag à 0, type par défaut 'livre'
    assert rows[1] == (2, "tbr", 0, "livre")
    assert rows[2] == (3, "read", 0, "livre")

    # Les tables filles ont survécu à la recreate batch (foreign_keys OFF).
    assert _query(db_path, "SELECT COUNT(*) FROM reading_session")[0][0] == 1
    assert _query(db_path, "SELECT COUNT(*) FROM highlight")[0][0] == 1

    # Le CHECK ck_book_type est actif : un type hors enum est refusé.
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO book (title, status, type, created_at, updated_at)"
                " VALUES ('X', 'tbr', 'roman', 'x', 'x')"
            ))
        raise AssertionError("le CHECK ck_book_type aurait dû refuser type='roman'")
    except IntegrityError:
        pass
    finally:
        engine.dispose()

    # Aucune valeur morte `wishlist` ne traîne en base.
    assert _query(db_path, "SELECT COUNT(*) FROM book WHERE status = 'wishlist'")[0][0] == 0


def test_downgrade_then_reupgrade_roundtrip(tmp_path):
    db_path = tmp_path / "m.db"
    cfg = _config(db_path)
    _upgrade_to_previous(cfg, db_path)

    _upgrade(cfg, db_path, TARGET)
    assert _query(db_path, "SELECT COUNT(*) FROM book WHERE is_wishlist = 1")[0][0] == 1

    # Downgrade : le wishlist repasse à l'ancien statut, les colonnes
    # disparaissent, les données filles restent.
    _downgrade(cfg, db_path, PREV_HEAD)
    cols = {row[1] for row in _query(db_path, "PRAGMA table_info(book)")}
    assert "is_wishlist" not in cols
    assert "type" not in cols
    assert _query(db_path, "SELECT status FROM book WHERE id = 1")[0][0] == "wishlist"
    assert _query(db_path, "SELECT COUNT(*) FROM reading_session")[0][0] == 1

    # Re-upgrade : le backfill refait le mapping — cycle propre.
    _upgrade(cfg, db_path, TARGET)
    assert _query(db_path, "SELECT status, is_wishlist, type FROM book WHERE id = 1")[0] == ("tbr", 1, "livre")
    assert _query(db_path, "SELECT COUNT(*) FROM reading_session")[0][0] == 1
