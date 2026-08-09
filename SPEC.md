# Marque-page — Spec technique de build

> Application de suivi de lecture auto-hébergée (clone fonctionnel de *Book Track*), conçue pour tourner sur Synology DS218+ via Docker.
> Document destiné à être découpé en tâches par des agents de code (OpenCode). Nom de projet provisoire : **Marque-page** (slug : `marquepage`) — à renommer librement.

---

## 0. Contexte & contraintes matérielles

| Élément | Valeur | Conséquence |
|---|---|---|
| NAS | Synology DS218+ (Celeron J3355, **x86_64/amd64**, 2–6 Go RAM) | Builds Docker en `linux/amd64`. Stack **léger obligatoire**. |
| Déjà hébergé | Plex, Immich, Paperless, Sonarr/Radarr, etc. | Budget RAM serré : viser **< 250 Mo idle** pour l'app. **Interdit** : JVM, MariaDB/MySQL, Postgres. |
| Conventions Docker | `PUID=1026`, `PGID=100`, bind mounts sous `/volume1/docker/` | à respecter à l'identique. |
| Réseau | Tailscale + reverse proxy existant | App exposée derrière le proxy, pas de port public en clair. |

**Verdict faisabilité : OUI**, à condition de respecter le stack léger ci-dessous. Un seul conteneur, SQLite, footprint minimal.

---

## 1. Stack technique (imposé)

- **Backend** : Python 3.12 + **FastAPI** + **SQLModel** (SQLAlchemy + Pydantic) + Uvicorn.
- **Base de données** : **SQLite** (fichier unique, mode WAL). Mono-utilisateur.
- **Frontend** : **React 18 + Vite + TypeScript + TailwindCSS + shadcn/ui**. Build statique servi par le backend.
- **PWA** : `vite-plugin-pwa` (manifest + service worker), installable iOS/Android/desktop.
- **Scan ISBN** : `@zxing/library` (caméra, compatible iOS Safari, contrairement à `BarcodeDetector`).
- **Conteneur** : image unique multi-stage (build front → runtime python-slim). Un seul process.
- **Migrations** : Alembic.
- **Tests** : pytest (backend), Vitest (front) — couverture des parsers et du matching KOReader en priorité.

Justification : tout est ultra-représenté dans les LLM (donc bien généré par les agents), léger en RAM, et cohérent avec ton expérience (Python fort, SQLite déjà utilisé sur *Lecteur*).

---

## 2. Modèle de données (SQLite — DDL de référence)

> L'agent doit générer ça via SQLModel + migrations Alembic. DDL fourni comme spécification de vérité.

```sql
-- LIVRES
CREATE TABLE book (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    subtitle            TEXT,
    isbn10              TEXT,
    isbn13              TEXT,
    publisher           TEXT,
    published_date      TEXT,           -- ISO ou année seule
    page_count          INTEGER,
    language            TEXT,
    description         TEXT,
    cover_path          TEXT,           -- chemin local servi par le NAS (jamais hotlink)
    cover_source        TEXT,           -- openlibrary | google | manual | upload
    status              TEXT NOT NULL DEFAULT 'tbr',
                        -- wishlist | tbr | reading | read | dnf | on_hold
    owned               INTEGER NOT NULL DEFAULT 1,  -- 0 pour wishlist
    rating              REAL,           -- 0.5 .. 5.0 (pas; null si non noté)
    current_page        INTEGER DEFAULT 0,
    current_percent     REAL DEFAULT 0,
    acquired_date       TEXT,
    -- IDs externes pour ré-enrichissement
    openlibrary_work    TEXT,
    openlibrary_edition TEXT,
    google_books_id     TEXT,
    koreader_md5        TEXT,           -- clé de matching KOReader (partial md5)
    notes               TEXT,           -- avis perso / review
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX idx_book_status ON book(status);
CREATE INDEX idx_book_koreader_md5 ON book(koreader_md5);

-- AUTEURS (m2m)
CREATE TABLE author (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    openlibrary_key TEXT
);
CREATE TABLE book_author (
    book_id   INTEGER REFERENCES book(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES author(id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, author_id)
);

-- TAGS & GENRES unifiés (kind = genre|tag)
CREATE TABLE label (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL,
    kind  TEXT NOT NULL DEFAULT 'tag',  -- genre | tag
    UNIQUE(name, kind)
);
CREATE TABLE book_label (
    book_id  INTEGER REFERENCES book(id) ON DELETE CASCADE,
    label_id INTEGER REFERENCES label(id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, label_id)
);

-- LECTURES (supporte les relectures = plusieurs entrées par livre)
CREATE TABLE read_entry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL REFERENCES book(id) ON DELETE CASCADE,
    started_at  TEXT,        -- date début de lecture
    finished_at TEXT,        -- date "livre lu"
    rating      REAL,
    review      TEXT,
    created_at  TEXT NOT NULL
);

-- SESSIONS DE LECTURE (cœur du besoin : durée + pages)
CREATE TABLE reading_session (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id         INTEGER NOT NULL REFERENCES book(id) ON DELETE CASCADE,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    duration_sec    INTEGER NOT NULL,    -- saisi ou calculé
    start_page      INTEGER,
    end_page        INTEGER,
    pages_read      INTEGER,             -- end_page - start_page (ou saisi)
    note            TEXT,
    source          TEXT NOT NULL DEFAULT 'manual', -- manual | timer | koreader
    koreader_hash   TEXT,                -- pour idempotence des imports KOReader
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_session_book ON reading_session(book_id);
CREATE INDEX idx_session_started ON reading_session(started_at);

-- HIGHLIGHTS / CITATIONS
CREATE TABLE highlight (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id         INTEGER NOT NULL REFERENCES book(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    note            TEXT,
    page            INTEGER,
    location        TEXT,                -- xpointer/chapitre KOReader
    chapter         TEXT,
    color           TEXT,
    source          TEXT NOT NULL DEFAULT 'manual', -- manual | koreader
    highlighted_at  TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_highlight_book ON highlight(book_id);

-- JOURNAL DES IMPORTS KOReader (idempotence)
CREATE TABLE koreader_import (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_sha256   TEXT NOT NULL,
    imported_at   TEXT NOT NULL,
    sessions_added INTEGER DEFAULT 0,
    books_matched  INTEGER DEFAULT 0,
    books_unmatched INTEGER DEFAULT 0
);
```

**Règles métier :**
- `Bibliothèque` (vue principale) = tous les livres avec `owned = 1` (donc tbr/reading/read/dnf/on_hold).
- `Pile à lire` = `status = 'tbr'`.
- `Wishlist` = `status = 'wishlist'` (et `owned = 0`).
- `current_percent` recalculé à chaque session (`end_page / page_count`) ou poussé par KOReader.

---

## 3. Intégrations métadonnées + couvertures (variantes)

Objectif : ajout par **ISBN** ou **titre**, récupération auto des métadonnées, et **proposition de plusieurs variantes de couverture** à choisir.

### Sources (par ordre de priorité)
1. **Open Library**
   - Par ISBN : `GET https://openlibrary.org/isbn/{isbn}.json` → édition + clé work.
   - Recherche titre : `GET https://openlibrary.org/search.json?q={query}&limit=10`.
   - **Variantes de couverture** : récupérer toutes les éditions d'un work via `GET https://openlibrary.org/works/{work_id}/editions.json`, puis pour chaque édition à `cover_i`/ISBN construire `https://covers.openlibrary.org/b/id/{cover_id}-L.jpg`.
2. **Google Books** (fallback + variantes complémentaires)
   - `GET https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}` ou `q={titre}` → `volumeInfo.imageLinks` (thumbnail, small, medium, large).

### Algorithme `lookup`
1. Si ISBN fourni → Open Library by ISBN ; sinon recherche titre (renvoyer top 10 candidats à l'utilisateur).
2. Agréger les **couvertures candidates** Open Library (toutes éditions du work) + Google Books → dédupliquer par URL/dimensions → trier par résolution décroissante.
3. Renvoyer au front : métadonnées + **liste de couvertures candidates** (URL + dimensions + source).
4. à la sélection, **télécharger la couverture localement** dans `covers/` (jamais de hotlink : respect vie privée + résilience). Redimensionner en 2 tailles (thumb 200px, full 600px) via Pillow.

> Tous les appels externes côté backend (le front ne tape jamais directement les APIs). Cache mémoire/disque court pour éviter le rate-limit.

---

## 4. Intégration KOReader (Kindle + livres physiques)

Tu lis sur **Kindle + KOReader** et des **livres papier**. Deux chemins coexistent :
- **Papier** → sessions saisies manuellement (+ timer in-app).
- **KOReader** → import automatique des stats.

### 4.1 Source de vérité : `statistics.sqlite3`
KOReader stocke ses stats dans `KOReader/settings/statistics.sqlite3`. C'est la mine d'or (sessions, durées, pages). Schéma de référence (à **introspecter** car il varie selon la version) :

```sql
-- Table book de KOReader
book(id, title, authors, notes, last_open, highlights, pages,
     series, language, md5, total_read_time, total_read_pages)

-- Données par page (reconstruire les sessions à partir d'ici)
page_stat_data(id_book, page, start_time, duration, total_pages)
-- NB: anciennes versions = table `page_stat`. Détecter la table présente.
```

### 4.2 Reconstruction des sessions (algorithme)
Pour chaque `id_book` :
1. Récupérer toutes les lignes `page_stat_data` triées par `start_time`.
2. Découper en **sessions** : nouvelle session dès qu'un écart entre deux `start_time` consécutifs dépasse un **seuil d'inactivité** (paramétrable, défaut **900 s = 15 min**).
3. Par session : `started_at = min(start_time)`, `duration_sec = Σ duration`, `start_page`/`end_page` = min/max page, `pages_read = end_page - start_page + 1`.
4. `source = 'koreader'`, `koreader_hash = sha256(id_book + started_at)` pour **idempotence** (ne pas réimporter une session déjà présente).

### 4.3 Matching livre KOReader → livre app
Le `md5` KOReader est un *partial md5* (échantillonné), pas un md5 de fichier complet → match parfait impossible à l'aveugle.
- Stratégie : match par **`koreader_md5`** si déjà connu ; sinon match flou par **(titre + auteur)** avec **étape de confirmation manuelle** dans l'UI (écran "Livres KOReader non rattachés").
- à la confirmation, **persister `koreader_md5` → book_id** → imports futurs 100 % automatiques.

### 4.4 Modes de récupération du fichier (du + simple au + automatisé)
- **MVP → Upload manuel** : bouton "Importer stats KOReader" dans Réglages → upload du `statistics.sqlite3` → parsing → preview du diff → confirmation.
- **Auto via dossier surveillé** : KOReader (cloud sync / dossier) dépose le fichier dans un dossier monté sur le NAS ; un watcher (watchdog) déclenche l'import. (Tu as Tailscale → le Kindle peut pousser le fichier.)
- **Optionnel (Phase 6) → serveur kosync intégré** : exposer les endpoints du protocole kosync (`/users/create`, `/users/auth`, `/syncs/progress`) pour la **progression live %** entre appareils. Limite connue : kosync ne transmet qu'un hash MD5 + % par document, **sans titre** → utile pour le % courant, pas pour les sessions.

### 4.5 Highlights KOReader
- Source : sidecars `.sdr/metadata.epub.lua` (ou export highlights KOReader en HTML/JSON).
- MVP : import via upload d'un export highlights ou parsing des sidecars déposés dans le dossier surveillé → table `highlight` avec `source='koreader'`, dédup par `(book_id, text, page)`.

---

## 5. API REST (FastAPI)

Préfixe `/api/v1`. Auth simple (1 user) : token bearer ou cookie de session + mot de passe unique (suffisant en réseau Tailscale privé).

```
# Recherche / enrichissement
GET    /lookup?isbn={isbn}                 -> métadonnées + couvertures candidates
GET    /lookup?q={titre|auteur}            -> top 10 candidats
GET    /lookup/covers?work={olid}&isbn=..  -> variantes de couverture seules

# Livres
GET    /books                  ?status=&tag=&genre=&author=&q=&sort=&page=
POST   /books                  -> création (depuis lookup ou manuel)
GET    /books/{id}
PATCH  /books/{id}             -> maj statut, note, couverture, tags...
DELETE /books/{id}
POST   /books/{id}/cover       -> upload couverture manuelle / sélection variante

# Statut rapide (pile à lire / wishlist / lu)
POST   /books/{id}/status      { status, finished_at? }

# Lectures (read_entry, relectures)
POST   /books/{id}/reads       { started_at, finished_at, rating, review }
PATCH  /reads/{id}
DELETE /reads/{id}

# Sessions de lecture
GET    /books/{id}/sessions
POST   /books/{id}/sessions    { started_at, duration_sec, start_page, end_page, note }
POST   /timer/start            { book_id }     -> session live (stockée côté client + serveur)
POST   /timer/stop             { book_id, end_page }
PATCH  /sessions/{id}
DELETE /sessions/{id}

# Highlights
GET    /books/{id}/highlights
POST   /books/{id}/highlights  { text, note, page, chapter, color }
PATCH  /highlights/{id}
DELETE /highlights/{id}

# Taxonomie
GET    /authors  | /labels?kind=genre|tag
GET    /authors/{id}/books

# KOReader
POST   /koreader/import        (multipart: statistics.sqlite3) -> diff preview
POST   /koreader/import/confirm { mappings:[{koreader_book_id, book_id}] }
GET    /koreader/unmatched

# Dashboard / stats
GET    /stats/overview         -> totaux (livres lus, temps total, pages, streak)
GET    /stats/timeline?range=  -> sessions agrégées par jour/semaine/mois
GET    /stats/by-genre | /stats/by-author

# Import/Export & admin
POST   /import/booktrack       (CSV/JSON export de Book Track) -> migration initiale
GET    /export                 -> dump JSON complet (sauvegarde)
```

---

## 6. Frontend — écrans & design

### Pages (responsive desktop + mobile, PWA)
1. **Bibliothèque** : grille couverture-first (les couvertures sont les héros, comme Book Track). Filtres : statut, auteur, genre, tag, recherche. Tri : titre, date ajout, note, progression.
2. **Détail livre** : couverture, métadonnées, progression (%), onglets *Sessions* / *Highlights* / *Lectures*, bouton "Démarrer une session".
3. **Ajout** : par **scan ISBN caméra** (zxing), par ISBN manuel, ou recherche titre → écran de **sélection de couverture** (galerie de variantes).
4. **Session active** : chrono plein écran (start/pause/stop), saisie page d'arrivée à la fin → crée la `reading_session`.
5. **Pile à lire** (TBR) : liste ordonnable.
6. **Wishlist** : livres souhaités (non possédés).
7. **Highlights** : flux global de citations, recherche plein texte, filtrage par livre.
8. **Stats / Dashboard** : temps total, livres/an, pages, streak, timeline (graph), répartition par genre/auteur.
9. **Vues filtrées** : par auteur, par tag, par genre.
10. **Réglages** : import KOReader, import Book Track, sauvegarde/export, seuil d'inactivité des sessions, mot de passe.

### Design system (dark, premium, couverture-first)
Tokens proposés (réutilise ta palette LPA pour cohérence visuelle si tu veux, sinon swap facile) :
```css
--bg:        #0a0908;   /* fond */
--surface:   #16140f;
--accent:    #c8a96e;   /* or */
--text:      #ece7df;
--muted:     #8a8275;
--font-display: "Cormorant Garamond", serif;
--font-ui:      "Instrument Sans", system-ui, sans-serif;
```
Principes : grilles de couvertures généreuses, ombres douces, transitions discrètes, mobile en bottom-nav (Bibliothèque / Ajouter / PAL / Stats / Réglages), desktop en sidebar.

---

## 7. Déploiement Docker (DS218+)

### Dockerfile (multi-stage, amd64)
```dockerfile
# --- build front ---
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build              # -> /web/dist

# --- runtime ---
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
COPY --from=web /web/dist ./static
ENV PUID=1026 PGID=100 TZ=Europe/Paris
EXPOSE 8000
CMD ["uv","run","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
```

### docker-compose.yml
```yaml
services:
  marquepage:
    build:
      context: .
      platforms: ["linux/amd64"]
    image: marquepage:latest
    container_name: marquepage
    restart: unless-stopped
    ports:
      - "8123:8000"                # à mapper derrière ton reverse proxy
    environment:
      - PUID=1026
      - PGID=100
      - TZ=Europe/Paris
      - APP_PASSWORD=change_me
      - SESSION_GAP_SEC=900
    volumes:
      - /volume1/docker/marquepage/data:/app/data        # SQLite + WAL
      - /volume1/docker/marquepage/covers:/app/covers
      - /volume1/docker/marquepage/koreader-inbox:/app/inbox  # dossier surveillé (optionnel)
    mem_limit: 384m              # garde-fou pour protéger le NAS
    cpus: 1.0
```
Notes : build en `linux/amd64` (le DS218+ est x86_64) ; `mem_limit` pour ne pas étouffer Plex/Immich ; Watchtower OK si tu publies l'image, sinon rebuild manuel.

---

## 8. Plan de build par phases (pour les agents)

> Chaque phase = un lot livrable testable. Critères d'acceptation explicites pour cadrer les agents.

**Phase 0 — Scaffold**
- Repo monorepo (`/backend`, `/frontend`), Dockerfile, compose, FastAPI "hello", shell React.
- → `docker compose up` sert une page et `/api/v1/health` répond.

**Phase 1 — Données + ajout de livres**
- Modèle SQLModel + migrations Alembic (schéma §2). Endpoint `/lookup` (Open Library + Google). CRUD `book`. Sélecteur de couvertures + download local + resize.
- → Ajouter un livre par ISBN récupère métadonnées + propose ≥ 2 couvertures ; couverture choisie servie localement.

**Phase 2 — Bibliothèque & taxonomie**
- Vues Bibliothèque (grille + filtres statut/auteur/genre/tag), Détail, PAL, Wishlist. Gestion tags/genres/auteurs.
- → Filtrer par auteur/genre/tag fonctionne ; déplacer un livre entre statuts marche.

**Phase 3 — Sessions & progression**
- Saisie manuelle de session, **timer in-app** (start/stop), recalcul `current_percent`, `read_entry` (relectures, dates début/fin), notation.
- → Une session ajoute durée + pages ; marquer "lu" enregistre `finished_at` ; le dashboard affiche temps total et timeline.

**Phase 4 — Highlights**
- CRUD highlights, recherche plein texte, flux global.
- → Créer/éditer un highlight et le retrouver par recherche.

**Phase 5 — KOReader (cœur différenciant)**
- Parser `statistics.sqlite3` (introspection de schéma), reconstruction des sessions (§4.2), matching + écran de rattachement (§4.3), import idempotent, journal `koreader_import`. Highlights KOReader.
- → Upload d'un `statistics.sqlite3` → sessions importées sans doublon ; rattachement d'un livre persiste le `koreader_md5`.

**Phase 6 — Finitions**
- PWA (manifest + SW + installable iOS), scan ISBN caméra (zxing), import Book Track (CSV), export/sauvegarde JSON, dossier surveillé KOReader, (optionnel) serveur kosync.
- → App installable sur iPhone ; scan d'un code-barres remplit l'ISBN ; export JSON régénérable.

---

## 9. Traçabilité du cahier des charges

| Besoin exprimé | Couvert par |
|---|---|
| Héberger sur NAS Docker | §7 (image amd64, conventions Synology) |
| Design moderne | §6 (design system dark, couverture-first) |
| Ajout par ISBN ou manuel | §3, API `/lookup`, `/books` |
| Scrap auto des couvertures + variantes | §3 (Open Library editions + Google Books, sélecteur) |
| Durée des sessions de lecture | §2 `reading_session.duration_sec`, §6 timer |
| Sessions avec pages lues + temps | §2, API `/books/{id}/sessions`, `/timer/*` |
| Livre lu avec dates | §2 `read_entry` (started_at/finished_at), `/books/{id}/status` |
| Classer par tag / auteur / genre | §2 `label`(kind), `author` m2m, §6 vues filtrées |
| Pile à lire | `status='tbr'` |
| Wishlist | `status='wishlist'`, `owned=0` |
| Voir toute la bibliothèque | §6 page Bibliothèque |
| Partie highlights | §2 `highlight`, §6 page Highlights |
| Connexion KOReader (data + sync) | §4 complet |

---

## 10. Découpage suggéré pour tes agents OpenCode

- `python-dev` : modèle de données, migrations, parsers (KOReader, Book Track), API FastAPI, tests pytest.
- `seo-technique` / generic : intégrations externes (Open Library, Google Books), watcher dossier.
- `css-ui` : design system, composants shadcn, pages, PWA, scan ISBN.
- Fichier `AGENTS.md`/`CLAUDE.md` racine : rappeler les contraintes (amd64, SQLite only, mem_limit, PUID/PGID, pas de hotlink de couverture).

> Conseil d'enchaînement : faire valider chaque phase (critères §8) avant de lancer la suivante, comme tu fais déjà en itératif.
