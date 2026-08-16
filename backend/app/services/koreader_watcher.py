"""Watcher du dossier surveillé KOReader (§4.4, décision 16/08).

La Kindle pousse son `statistics.sqlite3` en WebDAV vers le MN56 quand elle
est sur le même WiFi (IP locale directe, pas de Tailscale côté Kindle). Ce
module surveille `KOREADER_INBOX_DIR` et déclenche l'import.

Mécanisme : polling asyncio simple (30 s). Pas de watchdog — une nouvelle
dépendance native n'apporte rien pour un fichier qui arrive rarement sur un
volume monté localement.

Comportement (volontairement prudent, cf. décision 16/08) :
- Si TOUS les livres du fichier matchent déjà un livre de l'app par
  `koreader_md5`, l'import est appliqué immédiatement (auto-confirm) :
  sessions ajoutées (idempotence par `koreader_hash`), progression
  re-synchronisée.
- Sinon (livres non rattachés), le fichier est déplacé vers
  `KOREADER_PENDING_DIR` et N'EST PAS confirmé : l'écran « Livres KOReader
  non rattachés » (§4.3) prend le relais, l'utilisateur choisit les
  correspondances, puis `POST /koreader/import/confirm` applique tout.
- Le watcher ne suppose JAMAIS qu'un push est garanti : il réagit à la
  présence du fichier, rien de plus. Le déclenchement côté Kindle (script
  KUAL, action manuelle) reste à tester sur l'appareil réel.

La session est obtenue via une `session_factory` (injectable) : en
production c'est `Session(engine)` de app.db ; les tests fournissent une
factory branchée sur leur base fraîche. Sans ça, le watcher écrirait dans
une base différente de celle servie par l'API en environnement de test.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Callable

from sqlmodel import Session

from app import config
from app.db import engine
from app.routers.koreader import _build_book_previews, apply_koreader_import
from app.services.koreader import KoreaderError, parse_statistics

logger = logging.getLogger(__name__)

# Fréquence de scrutation du dossier (s). 30 s est large pour un fichier
# qui n'arrive que lors d'un passage sur le WiFi.
POLL_INTERVAL_SEC = 30.0

# Nom des fichiers attendus dans l'inbox.
_INBOX_PATTERNS = ("statistics.sqlite3", "*.sqlite3", "*.sqlite", "*.db")

# Sous-dossier où ranger les fichiers importés (évite de les re-voir, et
# garde une trace pour diagnostic sans polluer la bibliothèque).
_PROCESSED_DIRNAME = ".processed"


class KoreaderWatcher:
    """Scrute l'inbox KOReader en boucle et applique les imports automatiques."""

    def __init__(
        self,
        inbox_dir: Path | None = None,
        poll_interval: float = POLL_INTERVAL_SEC,
        session_factory: Callable[[], Session] | None = None,
    ):
        self.inbox_dir = inbox_dir or config.KOREADER_INBOX_DIR
        self.poll_interval = poll_interval
        self._session_factory = session_factory or (lambda: Session(engine))
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    # -- cycle de vie -------------------------------------------------------

    def start(self) -> None:
        """Lance la boucle de scrutation en arrière-plan (non bloquant)."""
        if self._task is not None and not self._task.done():
            return  # déjà lancé
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="koreader-watcher")

    async def stop(self) -> None:
        """Arrête la boucle et attend qu'elle se termine."""
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    # -- boucle -------------------------------------------------------------

    async def _run(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info("watcher KOReader : scrutation de %s", self.inbox_dir)
        while not self._stop.is_set():
            try:
                await asyncio.to_thread(self._scan_once)
            except Exception:
                # Une erreur isolée ne doit pas tuer la boucle : on loggue et
                # on reprend au prochain tick (le fichier reste en place).
                logger.exception("watcher KOReader : erreur pendant la scrutation")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass

    # -- un passage ---------------------------------------------------------

    def _scan_once(self) -> int:
        """Un passage de scrutation. Retourne le nombre de fichiers traités."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        processed_dir = self.inbox_dir / _PROCESSED_DIRNAME
        processed_dir.mkdir(parents=True, exist_ok=True)

        files: list[Path] = []
        for pattern in _INBOX_PATTERNS:
            files.extend(self.inbox_dir.glob(pattern))
        # Élimine les doublons (un même fichier peut matcher plusieurs
        # patterns) et le sous-dossier de traitement.
        seen: set[Path] = set()
        candidates: list[Path] = []
        for f in sorted(files):
            if f.is_file() and f.resolve() not in seen and processed_dir.resolve() not in f.resolve().parents:
                seen.add(f.resolve())
                candidates.append(f)

        handled = 0
        for path in candidates:
            if self._handle_file(path, processed_dir):
                handled += 1
        return handled

    def _handle_file(self, path: Path, processed_dir: Path) -> bool:
        """Traite un fichier : auto-import si tout matche, sinon pending.

        Retourne True si le fichier a été rangé (importé ou mis en attente),
        False en cas d'erreur (le fichier reste dans l'inbox).
        """
        sha = _file_sha256(path)
        try:
            stats = parse_statistics(path)
        except KoreaderError as exc:
            logger.warning("watcher KOReader : %s non importable (%s)", path.name, exc)
            return False

        with self._session_factory() as session:
            previews = _build_book_previews(
                session, stats, config.SESSION_GAP_SEC, _duration_factor(stats)
            )
            all_matched = all(p.matched for p in previews)

            if all_matched:
                result = apply_koreader_import(session, stats, file_sha256=sha)
                session.commit()
                logger.info(
                    "watcher KOReader : %s importé (sessions +%d, livres %d/%d)",
                    path.name,
                    result.sessions_added,
                    result.books_matched,
                    result.books_unmatched,
                )
                _archive(path, processed_dir)
                return True

            # Livres non rattachés : on garde le fichier pour la confirmation
            # manuelle. Le déplacer dans le pending le fait apparaître dans
            # `GET /koreader/unmatched` sans que le watcher le re-traite.
            dest = config.KOREADER_PENDING_DIR / f"{sha}.sqlite3"
            config.KOREADER_PENDING_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
            logger.info(
                "watcher KOReader : %s mis en attente (%d livres non rattachés)",
                path.name,
                sum(1 for p in previews if not p.matched),
            )
            return True


def _duration_factor(stats):
    """Calibre la durée (secondes vs millisecondes) — §4.2."""
    from app.services.koreader import detect_duration_factor

    return detect_duration_factor(stats.books, stats.rows)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _archive(path: Path, processed_dir: Path) -> None:
    """Range le fichier importé dans `inbox/.processed/`."""
    dest = processed_dir / path.name
    # `statistics.sqlite3` écrasé à chaque sync : on préfixe par le hash
    # pour conserver plusieurs versions si nécessaire.
    dest = processed_dir / f"{_file_sha256(path)[:12]}_{path.name}"
    shutil.move(str(path), str(dest))
