# Marque-page — Spec technique de build

> Application de suivi de lecture auto-hébergée (clone fonctionnel de *Book Track*), tournant en Docker sur le **MN56**.
> Document destiné à être découpé en tâches par des agents de code (OpenCode). Nom de projet provisoire : **Marque-page** (slug : `marquepage`) — à renommer librement.

> ⚠️ **Corrigé le 14/08/2026.** Cette spec a été écrite avant la décision Homelab P2/P3 (« NAS = stockage pur, MN56 = compute Docker ») et décrivait un déploiement sur le Synology DS218+. Les §0, §6, §7, §9 et §10 ont été mis à jour pour décrire la cible réelle. Les §1 à §5 et §8 n'ont pas bougé : ils restent la spécification de vérité pour le schéma, les intégrations, l'algorithme KOReader, l'API et le plan de build.

---

## 0. Contexte & contraintes matérielles

| Élément | Valeur | Conséquence |
|---|---|---|
| Hôte | **Firebat MN56** (Ryzen 7 8745HS, **x86_64/amd64**, 16 Go DDR5) | Builds Docker en `linux/amd64`. Stack léger recommandé, mais plus de budget RAM serré. |
| Déjà hébergé sur le MN56 | Portainer, feader-api, gametracker, OpenCode, OpenChamber | Cohabitation à surveiller sur les **ports**, pas sur la RAM. `mem_limit: 512m` suffit. |
| Conventions Docker | Bind mounts sous `/home/banserv/docker/<service>/`, pas de `PUID`/`PGID` | Ubuntu Server, pas DSM : les conventions Synology ne s'appliquent pas. |
| Réseau | Tailscale, **pas de reverse proxy** | Port bindé directement sur l'IP Tailscale `100.68.214.9`. Jamais `0.0.0.0`, jamais `127.0.0.1`. |
| Stockage | NVMe local du MN56 | ⚠️ **Non couvert par le backup 3-2-1** (qui ne protège que le NAS). Voir le trou de backup P4 du projet Homelab. |

**Verdict faisabilité : OUI.** Un seul conteneur, SQLite, footprint minimal — le stack léger reste le bon choix, non plus par contrainte matérielle mais par simplicité d'exploitation.

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
- **Auto via dossier surveillé** : décidé le 16/08/2026 avec Jordy. Pas de Tailscale sur la Kindle (jailbreak KUAL — module TUN non vérifié disponible, piste écartée). La Kindle est en WebDAV natif KOReader vers un serveur monté sur le **MN56** (pas le NAS, qui reste stockage/backup pur), joint en **IP locale directe quand Kindle et MN56 sont sur le même WiFi** — pas de sync hors de ce réseau, périmètre volontairement restreint pour rester simple. Un watcher (watchdog) sur le dossier déclenche l'import dès que le fichier arrive. `statistics.sqlite3` étant une base cumulative (toutes les sessions, WiFi ou non), un livre lu hors WiFi est **rattrapé automatiquement** au prochain sync grâce à la dédup par `koreader_hash` (§4.2) — pas de session perdue, juste un import différé. **Non vérifié à ce stade : le déclenchement effectif du push KOReader→WebDAV** (KOReader n'a pas nativement un "auto-upload au reconnect WiFi" confirmé ; il faudra probablement un script KUAL déclenché sur événement WiFi, ou une action manuelle dans KOReader). À tester sur la Kindle réelle avant de considérer ce mode "automatique" acquis.
- **Optionnel (Phase 6) → serveur kosync intégré** : exposer les endpoints du protocole kosync (`/users/create`, `/users/auth`, `/syncs/progress`) pour la **progression live %** entre appareils. Limite connue : kosync ne transmet qu'un hash MD5 + % par document, **sans titre** → utile pour le % courant, pas pour les sessions.

### 4.5 Highlights KOReader
- Source : sidecars `.sdr/metadata.epub.lua` (ou export highlights KOReader en HTML/JSON).
- MVP : import via upload d'un export highlights ou parsing des sidecars déposés dans le dossier surveillé → table `highlight` avec `source='koreader'`, dédup par `(book_id, text, page)`.

### 4.6 Import Book Track — format réel (vérifié le 16/08/2026)

> Basé sur un export réel de l'app (`booktracker.csv`, 77 lignes). **Ne plus supposer, ce format fait foi.** CSV, en-têtes en 1ère ligne, 43 colonnes :

```
createdAt, updatedAt, id, externalId, source, title, subtitle, externalLink, state,
types, isbn10, isbn13, releaseDate, originalReleaseDate, releaseYear, originalReleaseYear,
placeOfPublication, description, remoteImageUrl, thumbnailRemoteImageUrl,
externalAverageRating, userRating, pages, audiobookDuration, languages, purchaseDate,
purchasePrice, purchaseCurrency, series, seriesNumber, location, bookcase, shelf,
authors, narrators, illustrators, translators, publishers, categories, tags,
readingStatus, startReading, endReading
```

**Deux statuts indépendants, à ne pas confondre :**
- `state` — possession : `BOOKSHELF` (possédé) | `NOT_OWNED` (non possédé, ex. lu en bibliothèque) | `WISHLIST`.
- `readingStatus` — lecture : `unread` | `to-read` | `reading` | `read` | `dnf`.

Ces deux axes correspondent au besoin déjà noté (mémoire `data-model-extensions`) de séparer format-possession et statut de lecture — cet export confirme que le modèle à deux colonnes est le bon.

**Champs à parsing particulier :**
- `types` — un ou plusieurs formats, séparés par `;` : `EBOOK`, `AUDIOBOOK`, `HARDCOVER`, `PAPERBACK`, ex. `"PAPERBACK;EBOOK"`.
- `tags` — paires `nom|||#couleurHex`, plusieurs tags séparés par `;` : `"Cyberpunk|||#DB34F2;Megacorporations|||#00D2E0"`. La couleur vient de Book Track, pas forcément à reprendre (AGENTS.md interdit d'inventer un token `--accent` — ne pas importer ces couleurs dans le design system, seulement le nom du tag).
- `source` — provenance de la métadonnée d'origine dans Book Track (`GOOGLE_BOOKS`, `GOODREADS`, `ISBNDB`) — informatif, pas structurant pour l'import.
- `startReading` / `endReading` / `purchaseDate` — `YYYY-MM-DD`, chaîne vide si non renseigné (pas de `NULL` littéral).
- `series` / `seriesNumber` — texte libre, souvent vides même quand `series` est renseigné (`seriesNumber` peut manquer).
- `description` contient des retours à la ligne et guillemets internes échappés à la RFC 4180 standard — utiliser un parseur CSV, pas un split naïf sur `,`.
- Une seule ligne = une seule édition suivie ; un même titre peut apparaître deux fois avec deux `state`/`readingStatus` différents si l'utilisateur l'a retracké (ex. wishlist abandonnée puis relu) — dédupliquer par `id` (UUID Book Track), jamais par titre.

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

### Design system

> ⚠️ **Remplacé le 14/08/2026.** La proposition initiale (fond sombre `#0a0908`, accent or, Cormorant Garamond) a été écartée après maquettage. Elle invoquait « la palette LPA » qui n'existe plus sous cette forme — LPA est passé en clair, bleu marine `#051229`, Inter.
>
> **La source de vérité du design system est désormais `AGENTS.md` à la racine.** Ne pas réimplémenter les tokens ci-dessous, ils n'existent plus.

Direction retenue : **papier clair, encre noire, aucune couleur d'accent.** Fond sépia clair de liseuse, typographie serif de lecture, la couleur ne vient que des couvertures. Détail complet des tokens, des trois layouts et des points de rupture dans `AGENTS.md`.

Principes conservés : grilles de couvertures généreuses, ombres douces, transitions discrètes, mobile en bottom-nav (Bibliothèque / PAL / Ajouter / Stats / Réglages).

---

## 7. Déploiement Docker (MN56)

> ⚠️ **Réécrit le 14/08/2026.** Les fichiers réels du repo — `Dockerfile` et `docker-compose.yml` à la racine — **font foi**. Cette section les décrit, elle ne les remplace pas : en cas de divergence, corriger cette section, pas les fichiers.

Ce que le déploiement réel change par rapport à la version Synology :

| Point | Version Synology (abandonnée) | Version MN56 (réelle) |
|---|---|---|
| Bind du port | `"8123:8000"` derrière un reverse proxy | `"100.68.214.9:8123:8000"` — IP Tailscale directe, pas de proxy |
| Volumes | `/volume1/docker/marquepage/` | `/home/banserv/docker/marquepage/` |
| `PUID`/`PGID` | `1026` / `100` | **aucun** — convention DSM, sans objet sur Ubuntu |
| `mem_limit` | `384m` (protéger Plex/Immich) | `512m` |
| Node du build front | `node:20-slim` | `node:24-slim` |
| `platforms:` | `["linux/amd64"]` explicite | inutile — le MN56 *est* amd64, on build en natif |

**La règle de bind, à ne jamais confondre :**
- Côté **hôte** (`ports:` du compose) → `100.68.214.9`. Ni `0.0.0.0` (exposition publique), ni `127.0.0.1` (le téléphone et la tablette perdraient l'accès via le tailnet).
- Côté **conteneur** (`--host` d'uvicorn) → `0.0.0.0` est correct et nécessaire, sinon le mapping de port ne route rien. L'isolation vient de l'hôte.

**Volume `inbox` (dossier surveillé KOReader)** : prévu au §4.4, pas encore monté. À ajouter en Phase 6 sous `/home/banserv/docker/marquepage/koreader-inbox`.

**Variables d'environnement** : `APP_PASSWORD` et `SESSION_GAP_SEC` sont documentées dans `.env.example` mais **pas encore branchées** dans le compose — l'application ne les lit pas avant la Phase 1. Les câbler au moment où le code s'en sert, pas avant : un `env_file:` pointant vers un `.env` absent fait échouer `docker compose up`.

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
| Héberger en Docker auto-hébergé | §7 (MN56, bind Tailscale) — le NAS est du stockage pur depuis P2/P3 |
| Design moderne | `AGENTS.md` (papier clair, couverture-first) |
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

## 10. Agents — répartition réelle

> ⚠️ **Remplacé le 14/08/2026.** Le découpage suggéré ici renvoyait aux agents globaux `python-dev`, `seo-technique` et `css-ui`. Ces agents existent bien, mais ils sont écrits pour le stack **affi-build** (scrapers SEO, exports GSC, overrides GeneratePress) : leur périmètre n'a rien à voir avec cette app. Trois agents dédiés ont été créés à la place.

| Agent | Outil | Fichier | Périmètre |
|---|---|---|---|
| `backend-dev` | OpenCode | `.opencode/agent/backend-dev.md` | SQLModel, Alembic, API FastAPI, intégrations Open Library / Google Books, parsers KOReader et Book Track, pytest, Docker |
| `frontend-dev` | OpenCode | `.opencode/agent/frontend-dev.md` | React/TS : état, routing, client API, formulaires, PWA, zxing. **Pas le visuel.** |
| `design-ui` | Claude Code | `.claude/agents/design-ui.md` | Design system, composants, layouts, accessibilité. Épinglé sur Sonnet 5. |

**Le gate design traverse les deux outils** : toute tâche visuelle qui arrive côté OpenCode doit être renvoyée vers Claude Code, jamais implémentée sur place. Détail dans `AGENTS.md`.

> Conseil d'enchaînement inchangé : faire valider chaque phase (critères §8) avant de lancer la suivante.
