"""Fixtures pytest de Marque-page.

Points sensibles :
- Les env vars (`MARQUEPAGE_DB`, `MARQUEPAGE_COVERS`) doivent être posées
  AVANT tout import de `app.*` : config.py et db.py les lisent au niveau
  module. C'est fait ici, en tête de module.
- Le client HTTP du lookup et celui du téléchargement de couvertures sont
  remplacés par des `httpx.MockTransport` via `app.dependency_overrides` :
  aucun test ne tape le réseau.
"""

import os
import tempfile
from pathlib import Path

import httpx
import pytest

_TMP = Path(tempfile.mkdtemp(prefix="marquepage-tests-"))
os.environ["MARQUEPAGE_DB"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["MARQUEPAGE_COVERS"] = str(_TMP / "covers")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app.db import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import books as books_router  # noqa: E402
from app.routers import lookup as lookup_router  # noqa: E402
from app.services.metadata import MetadataClient  # noqa: E402


@pytest.fixture()
def db_engine(tmp_path):
    """Engine SQLite frais par test, avec le schéma créé."""
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    """TestClient branché sur `db_engine` + HTTP mockés."""

    def _override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_metadata_client(handler):
    """MetadataClient avec transport mocké (aucun réseau)."""
    transport = httpx.MockTransport(handler)
    return MetadataClient(transport=transport)


def make_covers_client(handler):
    """httpx.AsyncClient (covers) avec transport mocké."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(
        transport=transport,
        timeout=15.0,
        headers={"User-Agent": "marquepage-test"},
    )


def override_http_deps(handler):
    """Redirige `get_http_client` des routers books vers le client mocké."""
    async def _fake():
        return make_covers_client(handler)

    app.dependency_overrides[books_router.get_http_client] = _fake


def override_metadata_dep(metadata_client: MetadataClient):
    """Redirige `get_metadata_client` du router lookup."""

    def _fake() -> MetadataClient:
        return metadata_client

    app.dependency_overrides[lookup_router.get_metadata_client] = _fake
