"""Parser de l'export Book Track (CSV) — SPEC.md §4.6 (format réel vérifié).

Ce service est PUR : il ne touche ni à la base, ni au réseau. Il transforme
les octets d'un CSV en une liste d'objets `BooktrackRow` normalisés, prêts
pour l'insertion. Toute la logique de mapping vit ici, isolée et testable
unitairement sur le fichier réel `booktracker.csv`.

Format (43 colonnes, en-tête en 1ère ligne, RFC 4180) :
- `description` contient des retours à la ligne et guillemets échappés :
  le parsing passe par `csv.DictReader`, jamais par un split naïf.
- Deux statuts ORTHOGONAUX, à ne pas confondre :
  * `state`         — possession : BOOKSHELF | NOT_OWNED | WISHLIST
  * `readingStatus` — lecture   : unread | to-read | reading | read | dnf
- `types` multi-valeurs séparées par `;` (EBOOK, AUDIOBOOK, HARDCOVER,
  PAPERBACK) ; `tags` en paires `nom|||#couleur` séparées par `;` (la
  couleur est ignorée : pas de token accent dans le design system).
- Dates `YYYY-MM-DD` ou chaîne vide (jamais de `NULL` littéral).
- Dédup par `id` (UUID Book Track), jamais par titre — un même titre peut
  exister en deux éditions/statuts.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# state (possession) -> owned (0/1)
STATE_OWNED = {
    "BOOKSHELF": 1,
    "NOT_OWNED": 0,
    "WISHLIST": 0,
}

# readingStatus (lecture) -> status de l'app
READING_STATUS_MAP = {
    "unread": "tbr",
    "to-read": "tbr",
    "reading": "reading",
    "read": "read",
    "dnf": "dnf",
}

# types Book Track -> (format app, possession par défaut)
# La possession PAR format suit `state` (BOOKSHELF => possédé), donc
# `owned` est recalculé dans `_parse_row`, pas fixé ici.
BT_FORMAT_TO_APP = {
    "EBOOK": "digital",
    "AUDIOBOOK": "audio",
    "HARDCOVER": "physique",
    "PAPERBACK": "physique",
}

# Marqueurs « vide » que Book Track peut écrire (chaîne "nan", espaces…)
_EMPTY_TOKENS = {"", "nan", "NaN", "null", "None"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class BooktrackFormat:
    """Un format importé : type app + possession (dérivée de `state`)."""

    type: str
    owned: bool


@dataclass
class BooktrackRow:
    """Un livre normalisé, prêt pour l'insertion.

    Les champs de la base `book` sont exposés sous leur nom de colonne ;
    la taxonomie et les formats sont des listes résolues. `line_no` sert
    aux messages d'erreur de ligne.
    """

    line_no: int
    booktrack_id: str  # UUID Book Track — clé de dédup, jamais None (défendu à la validation)

    title: str
    subtitle: str | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = None
    language: str | None = None
    description: str | None = None
    status: str = "tbr"
    owned: int = 1
    rating: float | None = None
    acquired_date: str | None = None
    price_paid: float | None = None
    purchased_at: str | None = None
    series: str | None = None
    series_index: float | None = None
    cover_url: str | None = None
    cover_source: str = "booktrack"
    # Lecture associée (read_entry) — si status=read et dates présentes.
    read_started_at: str | None = None
    read_finished_at: str | None = None
    # Taxonomie
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # noms seuls, couleur ignorée
    genres: list[str] = field(default_factory=list)
    formats: list[BooktrackFormat] = field(default_factory=list)


@dataclass
class BooktrackParseResult:
    """Résultat du parsing : lignes valides + erreurs par ligne.

    Un CSV n'est pas atomique : une ligne mal formée ne doit pas faire
    perdre les 76 autres. `errors` liste `(line_no, raison)` pour un compte
    rendu à l'utilisateur.
    """

    rows: list[BooktrackRow] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)


class BooktrackParseError(Exception):
    """Erreur structurelle du fichier (pas un en-tête Book Track, etc.).

    Distinguée des erreurs par ligne : elle fait échouer tout l'import.
    """


# ---------------------------------------------------------------------------
# Helpers de nettoyage
# ---------------------------------------------------------------------------

def _clean(value: str | None) -> str | None:
    """Vide les marqueurs Book Track (`nan`, `null`…) et les espaces."""
    if value is None:
        return None
    value = value.strip()
    if value in _EMPTY_TOKENS:
        return None
    return value or None


def _clean_date(value: str | None) -> str | None:
    """Garde uniquement une date valide `YYYY-MM-DD`, sinon None."""
    value = _clean(value)
    if value and _DATE_RE.match(value):
        return value
    return None


def _clean_int(value: str | None) -> int | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(float(value))  # tolère "240" comme "240.0"
    except (ValueError, TypeError):
        return None


def _clean_float(value: str | None) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        return None
    return parsed if parsed == parsed else None  # NaN -> None


def _split_semicolon(value: str | None) -> list[str]:
    """Sépare une liste multi-valeurs `;` en entrées propres non vides."""
    value = _clean(value)
    if not value:
        return []
    return [p.strip() for p in value.split(";") if p.strip()]


def _parse_tags(raw: str | None) -> list[str]:
    """Tags Book Track `nom|||#couleur;nom2|||#couleur2` -> noms seuls.

    La couleur est un choix de Book Track, pas du design system : on ne
    l'importe pas (AGENTS.md interdit d'inventer un token accent).
    """
    tags: list[str] = []
    for part in _split_semicolon(raw):
        name = part.split("|||", 1)[0].strip()
        if name:
            tags.append(name)
    return tags


def _parse_formats(raw: str | None, owned: int) -> list[BooktrackFormat]:
    """Types Book Track (`EBOOK;AUDIOBOOK`) -> formats app, sans doublon.

    Les types inconnus (évolution future de Book Track) sont ignorés
    silencieusement plutôt que de faire échouer la ligne : le livre reste
    importable sans ses formats.
    """
    seen: set[str] = set()
    formats: list[BooktrackFormat] = []
    for raw_type in _split_semicolon(raw):
        app_type = BT_FORMAT_TO_APP.get(raw_type.upper())
        if app_type is None or app_type in seen:
            continue
        seen.add(app_type)
        formats.append(BooktrackFormat(type=app_type, owned=bool(owned)))
    return formats


def _map_status(state: str | None, reading_status: str | None) -> tuple[str, int]:
    """Combine les DEUX axes orthogonaux en (status, owned) pour l'app.

    Règles (SPEC §4.6) :
    - WISHLIST gagne sur tout : un livre souhaité est en wishlist, jamais lu
      dans l'app (la lecture est une information Book Track perdue ici).
    - Sinon `readingStatus` pilote le statut ; `state` pilote `owned`.
    - `readingStatus` vide ou inconnu -> `tbr` (statut par défaut de l'app).
    """
    state = _clean(state) or ""
    rs = _clean(reading_status) or ""

    if state == "WISHLIST":
        return "wishlist", 0

    owned = STATE_OWNED.get(state, 1)
    status = READING_STATUS_MAP.get(rs, "tbr")
    return status, owned


def _first_non_empty(values: list[str | None]) -> str | None:
    for v in values:
        cleaned = _clean(v)
        if cleaned:
            return cleaned
    return None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_booktrack_csv(data: bytes | str) -> BooktrackParseResult:
    """Parse les octets/texte d'un export Book Track en lignes normalisées.

    Lève `BooktrackParseError` si le fichier n'est pas un CSV Book Track
    (en-tête incomplet ou colonnes manquantes). Les erreurs par ligne sont
    collectées dans `result.errors` et n'arrêtent pas le reste.
    """
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8-sig")  # tolère un BOM éventuel
        except UnicodeDecodeError as exc:
            raise BooktrackParseError(f"encodage non UTF-8 : {exc}") from exc
    else:
        text = data

    reader = csv.DictReader(io.StringIO(text))
    required = {
        "id", "title", "state", "readingStatus", "types", "isbn10", "isbn13",
        "description", "pages", "languages", "purchaseDate", "purchasePrice",
        "series", "seriesNumber", "authors", "publishers", "categories",
        "tags", "startReading", "endReading", "remoteImageUrl",
    }
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise BooktrackParseError(
            f"en-tête incomplet, colonnes manquantes : {', '.join(sorted(missing))}"
        )

    result = BooktrackParseResult()
    for line_no, raw in enumerate(reader, start=2):  # 1 = en-tête
        try:
            result.rows.append(_parse_row(raw, line_no))
        except BooktrackParseError as exc:
            # Erreur structurelle d'une ligne (pas le fichier entier) :
            # on la compte et on continue.
            result.errors.append((line_no, str(exc)))
    return result


def _parse_row(raw: dict[str, str], line_no: int) -> BooktrackRow:
    booktrack_id = _clean(raw.get("id") or "")
    if not booktrack_id:
        raise BooktrackParseError("id (UUID Book Track) manquant")

    title = _clean(raw.get("title") or "")
    if not title:
        raise BooktrackParseError("title manquant")

    status, owned = _map_status(raw.get("state"), raw.get("readingStatus"))

    authors = _split_semicolon(raw.get("authors"))
    genres = _split_semicolon(raw.get("categories"))
    tags = _parse_tags(raw.get("tags"))
    formats = _parse_formats(raw.get("types"), owned)

    publisher = _first_non_empty([raw.get("publishers")])
    cover_url = _clean(raw.get("remoteImageUrl"))

    # La possession par format suit `state` : BOOKSHELF => possédé.
    # (`_parse_formats` reçoit `owned` calculé depuis `state`.)
    row = BooktrackRow(
        line_no=line_no,
        booktrack_id=booktrack_id,
        title=title,
        subtitle=_clean(raw.get("subtitle")),
        isbn10=_clean(raw.get("isbn10")),
        isbn13=_clean(raw.get("isbn13")),
        publisher=publisher,
        published_date=_clean_date(raw.get("releaseDate")),
        page_count=_clean_int(raw.get("pages")),
        language=_clean(raw.get("languages")),
        description=_clean(raw.get("description")),
        status=status,
        owned=owned,
        rating=_clean_float(raw.get("userRating")),
        purchased_at=_clean_date(raw.get("purchaseDate")),
        price_paid=_clean_float(raw.get("purchasePrice")),
        series=_clean(raw.get("series")),
        series_index=_clean_float(raw.get("seriesNumber")),
        cover_url=cover_url,
        read_started_at=_clean_date(raw.get("startReading")),
        read_finished_at=_clean_date(raw.get("endReading")),
        authors=authors,
        tags=tags,
        genres=genres,
        formats=formats,
    )
    return row
