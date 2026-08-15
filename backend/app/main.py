from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.routers import books, highlights, koreader, lookup, reads, sessions, stats, taxonomy


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


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Couvertures : toujours servies localement (jamais de hotlink, §3).
config.COVERS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/covers", StaticFiles(directory=config.COVERS_DIR), name="covers")

# Imports KOReader en attente de confirmation (fichier conservé entre
# /koreader/import et /koreader/import/confirm).
config.KOREADER_PENDING_DIR.mkdir(parents=True, exist_ok=True)

# Le front (build statique) est servi en dernier, en catch-all.
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
