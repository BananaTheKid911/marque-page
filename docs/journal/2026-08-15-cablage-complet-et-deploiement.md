# 15/08/2026 — Marque-page : câblage complet frontend-backend et premier déploiement réel

## Le point de départ

Le journal « quatre-vues » de ce matin se terminait sur une liste de choses à faire : handoff des 6 décisions produit vers le schéma, branchement des vues sur le vrai backend, écran d'ajout, export de sauvegarde. La session s'est déroulée en deux temps bien distincts, et ce document couvre les deux : **rattrapage** (7 commits du 15/08 non journalisés : le passage backend des décisions, le branchement frontend, la sauvegarde, les 4 écrans restants) puis **déploiement** (la première mise en production réelle du travail, ce soir).

Le déploiement a révélé un piège que rien dans les tests ne pouvait montrer : **le conteneur tournait depuis le 09/08 sur le scaffold Phase 0**. L'image `marquepage:latest` datait du tout début, tous les commits du 14–15/08 étaient committés mais invisibles. `/` servait encore le scaffold Vite (`<title>frontend</title>`), `/api/v1/books` répondait 404. Tout le travail du jour était là, dans le repo, et personne ne voyait rien.

---

## 1. Le handoff des six décisions produit (c2e4efc → b61778e)

Les six décisions tranchées avec Jordy ce matin (documentées dans le journal « quatre-vues ») ont été traduites en schéma, puis en contrat API, puis en endpoint.

### Schéma v2 (c2e4efc)

Cinq nouveautés structurelles dans `backend/app/models.py` + migration `ff98b093454f` :

- **`series`** (nouvelle table) + `book.series_id` (FK `SET NULL`) + `book.series_index` en **Decimal** — les hors-série 1.5 existent, un float ne suffit pas.
- **`book_format`** : le format n'est pas une colonne de `book` mais une table fille `(book_id, format, owned)` — parce que format et possession sont **orthogonaux** (Jordy peut posséder le papier d'un livre et avoir emprunté le digital). Le CHECK restreint format à `physique|digital|audio`.
- **`book.price_paid` / `purchased_at`** : un champ chacun, à remplir seulement à l'achat.
- **`book.is_primary_reading`** : flag exclusif parmi les `reading` — la contrainte est **réelle**, pas seulement dans le code : un index partiel unique (`WHERE is_primary_reading = 1`). Deux livres primaires simultanés sont physiquement impossibles en base, même si une requête concurrente tente le coup.
- **`book.tbr_rank` / `tbr_note`** : la Pile à lire devient une sélection ordonnée, distincte du simple filtre `status='tbr'`.

La migration a dû être écrite en **mode batch** avec `PRAGMA foreign_keys=OFF` autour de la recréation de `book` — sans ça, les `ON DELETE CASCADE` des tables filles (`reading_session`, `highlight`, …) emportaient les données à chaque upgrade. Vérifié par exécution : upgrade/downgrade avec données, FK, CHECK et index partiel tous effectifs.

**Règle métier `tbr → reading` à trois chemins**, câblée ici :
1. `POST /timer/start` — automatique ;
2. import KOReader apportant des sessions nouvelles — automatique, mais seulement si `sessions_added > 0` (un re-import idempotent ne rebascule rien) ;
3. `POST /books/{id}/status` et `PATCH` — manuel, exposé.

Cohérence des états dépendants : quitter la PAL libère `tbr_rank` (la note est conservée), cesser d'être `reading` libère `is_primary_reading`.

### Contrat API (c890090)

`BookOut`/`BookCreate`/`BookUpdate` exposent tout le v2 : `series` (upsert par nom), `series_index`, `formats` (possession par format, **remplacement complet** à chaque PATCH — pas de cumul silencieux), `price_paid`, `purchased_at`, `is_primary_reading`, `tbr_rank`, `tbr_note`. Ajout de `GET /series` + `GET /series/{id}/books` (filtre série, tri par tome) et `GET /books?sort=tbr_rank`.

Trois règles métier verrouillées par des **422 explicites**, jamais de vidage silencieux :
- primaire exclusif : `PATCH is_primary_reading=true` désélectionne l'actuel **dans la même transaction** (l'index partiel est le filet), et refuse hors statut `reading` ;
- wishlist sans prix : écrire `price_paid`/`purchased_at` sur un livre `wishlist` → 422 sur tous les chemins ;
- `tbr_rank` dérivé du statut : forcé à `NULL` hors de la PAL.

Détail technique au passage : `series_index` est resté `Decimal` côté modèle (c'est ce que renvoie la colonne `NUMERIC` de SQLite) et converti en `float` au contrat — ça a éliminé un warning Pydantic traqué jusqu'au `model_dump()`.

### Reorder transactionnel (b61778e)

La poignée de drag-and-drop du front avait besoin de son endpoint : `POST /books/tbr/reorder` avec un payload = **ordre complet voulu** (`book_ids`, 1 = prochain lu). Points importants :

- **Validation stricte AVANT toute modification** : id inexistant, livre non-tbr, doublon, liste vide → 422. Une liste périmée se recharge, elle ne se corrige pas en silence.
- **Dérangement global puis renumération 1..n en un commit** ; les livres tbr non listés retombent en fin de liste (rang `NULL`).
- Réponse = la PAL ordonnée complète, sans round-trip.
- Piège Starlette contourné : la route est déclarée **avant** `POST /{book_id}/status`, sinon Starlette matcherait `tbr` contre `book_id` et répondrait 422 au lieu d'appeler l'endpoint.

Vérifié : 8 tests dédiés (179 au total), dont l'atomicité (une liste invalide ne laisse aucune trace).

---

## 2. Le branchement frontend (079b113) : la fin du 100 % mock

Jusqu'ici le front vivait sur `mock-data.ts` et un routage QA dans `App.tsx`. Tout est remplacé par un **client HTTP réel** :

- `frontend/src/lib/api.ts` : le seul endroit qui appelle le réseau, préfixe relatif `/api/v1` (le backend sert le build et l'API depuis la même origine, jamais de CORS). **Mapper snake_case → camelCase** : si le payload diverge du contrat, la validation échoue ici plutôt que de contaminer l'UI.
- `context/books.tsx` : la lecture principale (carte « En cours ») + une version de données (`booksVersion`) incrémentée après chaque mutation serveur — les pages s'en servent comme dépendance de refetch sans round-trip explicite.
- **react-router** : les deep-links SPA (`/livres/5`, `/pile-a-lire`) fonctionnent au rechargement — c'est le `main.py` qui le permet (voir §4).
- `mock-data.ts` supprimé ; les pages sont rebranchées : Bibliothèque (filtres réels + mode série), PAL (reorder dnd-kit → `/tbr/reorder`, 422 → reload), Détail (chrono persistant, passage tbr→reading, lecture principale, « marquer comme lu »), Wishlist.

---

## 3. La sauvegarde comme filet de sûreté, pas un confort (add2090)

La base et les couvertures vivent sur le **NVMe local du MN56, hors backup 3-2-1** (celui-ci ne protège que le NAS). L'export/import JSON prévu à la Phase 6 est donc une fonctionnalité de sûreté. Deux endpoints :

- **`GET /api/v1/export`** → archive ZIP `marquepage-backup-YYYY-MM-DD.zip` contenant :
  - `marquepage.json` : dump complet `format_version 1` (books sous forme `BookOut` résolue, series, sessions avec `koreader_hash`, highlights, lectures) — **même forme que l'API**, pas une deuxième vérité à maintenir ;
  - `covers/` : les fichiers locaux embarqués (les uploads manuels seraient irrécupérables sinon).
- **`POST /api/v1/import`** → restauration miroir, **remplacement complet** :
  - une seule transaction (delete + réinsertion avec ids préservés) — tout échec = rollback, rien ne change ;
  - réinsertion via les helpers de création de `books.py` (même chemin que l'API, pas un code parallèle) ;
  - refus 422 AVANT toute modification (pas un zip, `marquepage.json` absent, `format_version` inconnu) ;
  - couvertures extraites après le commit, garde anti zip-slip.

Le `main.py` a reçu au passage le **catch-all SPA** : `StaticFiles(html=True)` ne sert la racine que pour `/`, pas pour les routes react-router — sans catch-all, recharger `/livres/5` donnait 404. Comportement verrouillé par `tests/test_spa.py` (deep-links → index, fichiers réels servis, API inconnue → 404).

---

## 4. Les quatre écrans sans couverture et leur câblage (40ac014 + b789262)

Design-ui a dessiné les écrans manquants du gate visuel (Ajouter, Stats, import KOReader, fin de session) sur données mock, en reprenant les **contrats d'API à l'octet près** depuis les routers réels — pour qu'aucune adaptation ne soit nécessaire au branchement. Puis frontend-dev a tout branché sur le backend réel et supprimé les mocks restants (`stats-mock.ts`, `mock-results.ts`) :

- **`/ajouter`** : onglets ISBN / titre-auteur, panneau scan (états idle/scanning/not-detected + saisie manuelle en voie parallèle, pas en repli), résultats de recherche, **sélection de couverture parmi plusieurs candidats**. Le flux réseau : `GET /lookup?isbn=` et `?q=`, variantes via `GET /lookup/covers` chargées à la sélection du candidat, création via `POST /books` — la variante choisie part en `cover_url`, **le backend la télécharge localement** (jamais de hotlink, §3 de la spec). Scan caméra via `@zxing/library` (`lib/use-isbn-scanner.ts`, vraie `<video>` dans `IsbnScanPanel`).
- **`/stats`** : streak en chiffre 34 px (seule masse dominante de l'écran), timeline day/week/month en barres CSS mono-ton, répartitions genre/auteur, états vides couverts.
- **`/reglages/import-koreader`** : flux en trois temps upload → aperçu → rattachement manuel (score de similarité en **label texte**, pas en badge coloré — cohérent avec l'absence d'accent) → confirmation.
- **Fin de session** (`SessionEndControl`) : remplace le `window.prompt` natif par un panneau inline (pas de modale, aucun pattern de dialog n'existait encore) — le bouton « Arrêter le chrono » devient le panneau, le CTA « Confirmer » hérite de la masse noire.

---

## 5. Le déploiement : le piège du « healthy mais cassé »

L'image en prod datait du 09/08. Avant de la remplacer, il fallait régler un problème que rien dans les tests ne couvrait : **rien ne crée les tables en production**. Le `Dockerfile` lançait `uvicorn` directement ; `create_all` n'existe que dans les fixtures de test (`tests/conftest.py`), et aucune migration Alembic n'était exécutée au démarrage. Sur le volume `data/` vide, le nouveau code aurait démarré, le healthcheck `/api/v1/health` serait passé (il ne touche pas la base)… et **toutes les routes métier auraient planté** (`no such table: book`). Le conteneur aurait été marqué *healthy* en étant cassé — le pire des états, car plus rien ne le signale.

Correctif apporté au `Dockerfile` :
- **`COPY backend/alembic.ini` + `COPY backend/alembic`** — sans eux, `alembic upgrade head` échouerait dans le conteneur (ils n'étaient jamais copiés) ;
- **`CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]`** — la migration est idempotente (ne rejoue que ce qui manque), donc sûre à chaque redémarrage.

Avant le rebuild, la migration a été **exécutée à blanc sur une base vierge** dans `/tmp` : `36ce8285e200` puis `ff98b093454f`, 13 tables créées, `alembic_version = ff98b093454f`. Puis `docker compose up -d --build` (image remplacée, conteneur recréé) et vérification par exécution sur le conteneur réel :

| Vérification | Résultat |
|---|---|
| Logs du conteneur | migrations exécutées puis uvicorn démarré |
| `GET /api/v1/health` | `{"status":"ok"}` |
| `GET /api/v1/books` | `200 {"items":[],"total":0,…}` — preuve que les tables existent |
| `GET /api/v1/export` | archive ZIP valide (`marquepage.json` + covers) |
| `GET /` | `<title>Marque-page</title>` — fini le scaffold « frontend » |
| `GET /pile-a-lire` (rechargement) | 200 — le catch-all SPA répond |
| `GET /api/v1/nope` | 404 — les routes API restent hors du catch-all |
| Volume NVMe | `marquepage.db` créé, WAL actif (`.db-wal`/`.db-shm` présents), version `ff98b093454f` |

**Captures headless** produites aux trois formats (desktop 1440×900, mobile 390×844, tablette 1500×960) via le Chromium de la recette du journal « fondations design » (dépendances `.deb` extraites sans root, `LD_LIBRARY_PATH`). Le DOM rendu au desktop confirme le vrai front : `shell-frame`, `shell bg-paper`, `shell__topnav/sidebar/rail/bottomnav`, tokens papier (`text-ink`, `border-line`), carte « En cours » dans son état vide (« Aucun livre en cours » — normal, base vierge). Le DOM mobile confirme la `bottomnav` et aucune erreur JS.

**Limite assumée** : le modèle d'IA de cette session ne sait pas lire les images — les trois captures existent (`/tmp/opencode/mp-{desktop,mobile,tablet}.png`) mais leur rendu visuel final est à valider par Jordy.

---

## ✅ Ce qui a été fait

- **Backend** : schéma v2 (series, formats×possession, achat, lecture principale exclusive, PAL ordonnée) + migration batch vérifiée ; contrat API des 6 décisions ; `POST /books/tbr/reorder` transactionnel ; règle `tbr→reading` à trois chemins.
- **Frontend** : client HTTP réel (`lib/api.ts`, mappers), contexte lecture principale + invalidation, react-router, deep-links SPA ; Bibliothèque/PAL/Détail/Wishlist rebranchés sur le vrai backend.
- **Sauvegarde** : `GET /export` (ZIP : JSON format API + covers) et `POST /import` (restauration transactionnelle, refus 422 avant modification, anti zip-slip).
- **Design** : 4 écrans sans couverture (Ajouter, Stats, import KOReader, fin de session) dessinés puis câblés ; scan caméra zxing intégré (non testé sur appareil réel, pas de caméra dans l'env).
- **Déploiement** : `Dockerfile` corrigé (COPY alembic + migration au démarrage), rebuild, conteneur sain, endpoints vérifiés par exécution, captures headless aux 3 formats.
- 199 tests backend verts, `tsc` + `vite build` + `oxlint` propres.

## Prochaine session

1. Jordy valide visuellement les captures (`/tmp/opencode/mp-*.png`) et l'app en vrai sur téléphone/tablette/desktop.
2. Phase 6 restante : **PWA** (`vite-plugin-pwa` — toujours pas installé), **import Book Track** (parser CSV/JSON — inexistant), **dossier surveillé KOReader** (volume `inbox` + watcher — jamais monté).
3. Trancher la couleur de signal (états abandonné/erreur) — les écrans sans couverture existent désormais, c'est le moment.
4. Ajouter des tests front (Vitest) — SPEC §1 l'exige, aucun test front n'existe.
5. **Committer cette session** (Dockerfile + journal) — demander à Jordy avant.

---

## Mini-glossaire

| Terme | Définition |
|---|---|
| **Index partiel unique** | Index SQLite avec une clause `WHERE` — ici `WHERE is_primary_reading = 1`. L'unicité ne s'applique qu'aux lignes qui passent le filtre : deux livres `reading` peuvent coexister, mais un seul peut être primaire. |
| **Mode batch (Alembic)** | `batch_alter_table` réécrit la table pour les opérations que SQLite ne supporte pas en place (modifier une colonne, ajouter une FK). `PRAGMA foreign_keys=OFF` autour évite que les CASCADE emportent les données filles pendant la recréation. |
| **Catch-all SPA** | Route FastAPI en fin de chaîne qui sert `index.html` pour tout chemin non API. Sans elle, les routes react-router répondent 404 au rechargement d'onglet. |
| **Remplacement complet** | Sémantique d'écriture : le PATCH reçoit l'état voulu et l'applique en entier, plutôt que de fusionner avec l'existant. Pas de cumul silencieux. |
| **422 avant modification** | L'API refuse la requête (validation) avant de toucher la base — une liste périmée se recharge côté client, elle ne se « corrige » pas en silence. |
| **Healthy mais cassé** | État où le healthcheck passe (il ne touche pas la base) alors que toutes les routes métier plantent. Causé ici par l'absence de migration au démarrage. |
| **`format_version`** | Champ de version dans l'export JSON — l'import refuse toute archive de version inconnue plutôt que d'interpréter un format futur. |
| **Zip-slip** | Attaque où un nom de fichier `../../etc/passwd` dans une archive écrit hors du dossier d'extraction. Garde : vérifier que chaque chemin résout bien dans le dossier cible. |
