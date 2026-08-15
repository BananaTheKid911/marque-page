from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.routers import backup, books, highlights, koreader, lookup, reads, sessions, stats, taxonomy


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Fermeture propre des clients HTTP singleton (pool de connexions).
    await books.close_http_client()
    await lookup.close_metadata_client()


app = FastAPI(title="Marque-page", lifespan=lifespan)

app.include_router(lookup.router, prefix="/api/v1")
app.include_router(books.router, prefix="/api/v1")
app.include_router(taxonomy.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(reads.router, prefix="/api/v1")
app.include_router(highlights.router, prefix="/api/v1")
app.include_router(koreader.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(backup.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Couvertures : toujours servies localement (jamais de hotlink, §3).
config.COVERS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/covers", StaticFiles(directory=config.COVERS_DIR), name="covers")

# Imports KOReader en attente de confirmation (fichier conservé entre
# /koreader/import et /koreader/import/confirm).
config.KOREADER_PENDING_DIR.mkdir(parents=True, exist_ok=True)

# Le front (build statique) est servi en catch-all SPA : les routes API et
# /covers sont enregistrées AVANT et gagnent toujours ; tout autre chemin
# sert le fichier réel s'il existe, sinon index.html. Sans ça, les routes
# react-router (`/livres/5`, `/pile-a-lire`) répondraient 404 au
# rechargement d'onglet — `StaticFiles(html=True)` ne sert la racine que
# pour « / ». Verrouillé par tests/test_spa.py.
static_dir = Path(__file__).resolve().parent.parent / "static"


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    candidate = static_dir / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    index = static_dir / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend non construit")
    return FileResponse(index)
