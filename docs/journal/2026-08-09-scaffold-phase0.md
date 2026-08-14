# P4 — Marque-page : scaffold Phase 0 (FastAPI + React, Docker sur le MN56)

**Date** : 09/08/2026
**Projet** : Homelab Mini PC — P4 (Migration services), lot "apps custom"
**Machines** : `NuxBanana` (Fedora, juste pour la correction du fichier de spec collé en chat) → `bananaserver` (Ubuntu Server, MN56, où vit tout le code et où tourne le conteneur)
**Tâche Notion** : `[Homelab P4] Apps custom — Marque-page` (page `3b71221c1008818c80fee727154ede4c`, nouvellement créée, Statut **En cours**)
**Suite de** : [P4 — reader-like-app : état des lieux](2026-08-09-p4-reader-like-app-etat-des-lieux.md) (c'est en clarifiant le scope de reader-like-app que Marque-page — "l'autre app qui sera stockée sur le MN56" — est arrivée sur la table)

## Contexte

Jordy avait déjà un fichier `SPEC.md` pour un projet "Marque-page" : un clone fonctionnel de *Book Track* (suivi de bibliothèque perso), avec un vrai différenciant — l'import des statistiques de lecture KOReader (temps passé, pages lues, matching par hash partiel) depuis un Kindle. Contrairement à reader-like-app, aucun code n'existait encore : seulement ce document de spec, jamais construit.

## 1. Un fichier collé avec un problème d'encodage

Le `SPEC.md` collé dans le chat avait ses accents corrompus (`Ã©` au lieu de `é`, `Ã ` au lieu de `à`, `â` à la place de tirets ou flèches...). C'est le symptôme classique d'un texte UTF-8 réinterprété comme Latin-1/Windows-1252 puis re-sauvegardé — souvent causé par un copier-coller entre deux outils qui ne s'accordent pas sur l'encodage.

Plutôt que de laisser ce texte corrompu entrer dans le repo, un script Python a reconstruit les bons caractères à partir d'une table de correspondance (`Ã©` → `é`, `Ã¢` → `â`, `Å` → `œ`, etc.), avec quelques ajustements à la main pour les tirets/flèches ambigus (`â` pouvait vouloir dire aussi bien "—" qu'une flèche "→" selon le contexte). Petit rappel utile : un simple `texte.encode('latin1').decode('utf-8')` ne suffit pas toujours — ici certains octets de contrôle avaient été perdus en route, donc une correspondance caractère par caractère a été nécessaire.

## 2. Vérifier les prérequis sur le MN56 avant de commencer

```bash
ssh mn56 "docker --version && docker compose version"
ssh mn56 "df -h ~ && ls -la ~/docker/"
```

- **Docker 29.7.2 / Compose v5.4.0** déjà en place (hérité de P2).
- **432 Go libres** sur le NVMe — largement suffisant.
- Le dossier `~/docker/` existe déjà avec `gametracker/` et `plex/` dedans — confirme la convention "données persistantes des conteneurs sous `~/docker/<service>/`, séparément du code sous `~/projects/<repo>`" déjà établie pour game-tracker.

## 3. La spec ciblait le mauvais endroit — troisième fois

Comme `lecteur-backend` et l'ancien `deploy.sh` de game-tracker, `SPEC.md` était écrit pour le Synology DS218+ :
- Conventions `PUID=1026`/`PGID=100` — un mécanisme LinuxServer.io/Synology pour faire tourner un conteneur sous l'UID d'un utilisateur DSM existant. **Sans objet sur Ubuntu Server** : une image `python:3.12-slim` brute n'interprète pas ces variables (elles auraient juste traîné, inertes, dans le `docker-compose.yml`).
- Chemins `/volume1/docker/marquepage/...` — c'est l'arborescence des dossiers partagés DSM. Remplacé par `/home/banserv/docker/marquepage/...`, la convention déjà en place sur le MN56.
- `mem_limit: 384m` dimensionné pour cohabiter avec Plex/Immich sur 2-6 Go de RAM NAS. Remplacé par `512m` — toujours un garde-fou (bonne pratique même avec beaucoup de RAM disponible), mais plus la contrainte serrée d'origine.
- `platforms: ["linux/amd64"]` — supprimé : on build nativement sur le MN56 (qui est lui-même amd64), pas de cross-compilation nécessaire.

## 4. Le port : Tailscale direct, pas "derrière un reverse proxy"

La spec disait "App exposée derrière le proxy" sans préciser lequel. Plutôt que de deviner, vérification de comment les services déjà en prod sur le MN56 bindent réellement leurs ports :

```bash
ssh mn56 "ss -tlnp | grep -E '9443|4000|3000'"
```

```
100.68.214.9:3000   ← OpenChamber (serveur OpenCode)
0.0.0.0:4000         ← game-tracker  ⚠️
100.68.214.9:9443   ← Portainer
```

Portainer et OpenChamber confirment le pattern à suivre : binder directement sur l'IP Tailscale du MN56 (`100.68.214.9`), pas sur `0.0.0.0`. C'est ce qui a été fait dans le `docker-compose.yml` de Marque-page :

```yaml
ports:
  - "100.68.214.9:8123:8000"
```

**Découverte en marge** : `game-tracker` est le seul service bindé sur `0.0.0.0:4000` — donc potentiellement joignable au-delà de Tailscale (tout le LAN, au minimum), contrairement à la règle absolue du projet ("jamais de port exposé, Tailscale uniquement"). Pas corrigé dans cette session — c'est un service en prod, la décision de le rebinder (et de redémarrer le conteneur) appartient à Jordy. Signalé, pas touché.

## 5. Scaffold du monorepo — versions vérifiées, pas devinées

Plutôt que d'écrire à la main un `package.json` avec des numéros de version tapés au hasard, le vrai outil officiel a été utilisé directement sur le MN56 (qui a Node v22 installé) :

```bash
ssh mn56 "cd ~/projects/marque-page && npm create vite@latest frontend -- --template react-ts"
```

Résultat : React 19.2.8, Vite 8.2.1, TypeScript 6.0.2 — les vraies versions du jour, avec un `package-lock.json` généré ensuite via `npm install` pour des builds reproductibles.

Côté backend, `pyproject.toml` minimal (FastAPI + Uvicorn seulement — SQLModel/Alembic/etc. sont pour la Phase 1, pas la Phase 0) :

```python
# backend/app/main.py
@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

Le `uv.lock` (nécessaire pour le `RUN uv sync --frozen` du Dockerfile) a été généré sans installer `uv` sur l'hôte, via un conteneur jetable :

```bash
docker run --rm -v $(pwd):/backend -w /backend python:3.12-slim sh -c "pip install -q uv && uv lock"
```

**Piège rencontré** : ce conteneur tourne en root, donc le `uv.lock` généré appartenait à `root` sur le disque du MN56 — pas gênant pour Docker, mais gênant pour éditer/committer le fichier ensuite en tant que `banserv`. Pas de `sudo` interactif configuré sur le MN56 (pas de mot de passe passé en clair, comportement voulu). Fix : un second conteneur jetable (`alpine`) pour faire le `chown` à la place de `sudo` :

```bash
docker run --rm -v ~/projects/marque-page/backend:/backend alpine chown 1000:1000 /backend/uv.lock
```

## 6. Build et vérification

```bash
docker compose build   # ~3s, tout en cache sauf le premier run
docker compose up -d
curl http://100.68.214.9:8123/api/v1/health   # → {"status":"ok"}
curl http://100.68.214.9:8123/                # → la page Vite
```

Healthcheck du conteneur : `healthy` après quelques secondes. Les deux critères d'acceptation de la Phase 0 (§8 de `SPEC.md`) sont remplis.

## 7. Commit

Identité git déjà configurée globalement sur le MN56 depuis game-tracker (`BananaTheKid911`), donc pas de setup supplémentaire. `git status` vérifié avant le commit : rien de sensible (pas de `.env`, `node_modules`/`dist` bien ignorés).

```
1edd579 Phase 0 -- scaffold monorepo FastAPI + Vite/React, Docker MN56 Tailscale-only
```

## ✅ Ce qui a été fait

- Corrigé l'encodage du `SPEC.md` collé (mojibake UTF-8/Latin-1) avant de l'intégrer au repo.
- Créé le repo `~/projects/marque-page` directement sur le MN56 (convention P6c : le code y vit, pas sur Fedora).
- Retargeté la spec Synology → MN56 : conventions PUID/PGID et chemins `/volume1/docker/` abandonnés, port bindé sur l'IP Tailscale plutôt que `0.0.0.0`.
- Scaffoldé le monorepo (`backend/` FastAPI + `frontend/` Vite/React) avec les vraies versions actuelles, lockfiles générés et committés pour les deux (`uv.lock`, `package-lock.json`).
- Build + démarrage + vérification : `/api/v1/health` répond, la page React est servie, healthcheck vert.
- Repéré et signalé (sans corriger) que `game-tracker` est exposé sur `0.0.0.0:4000` au lieu de l'IP Tailscale — à traiter dans une session dédiée.
- Créé la tâche Notion dédiée à Marque-page (page `3b71221c1008818c80fee727154ede4c`), statut **En cours**.

## Prochaine session

Deux sujets distincts, à ne pas mélanger :
1. **Marque-page — Phase 1** : modèle de données SQLModel + migrations Alembic (schéma déjà défini dans `SPEC.md` §2), endpoint `/lookup` (Open Library + Google Books), CRUD `book`, sélecteur de couvertures.
2. **Sécurité — game-tracker** : décider avec Jordy s'il faut rebinder le port 4000 sur l'IP Tailscale (implique un redémarrage du conteneur en prod) et vérifier s'il y a une exposition réelle au-delà du LAN (routeur, port forwarding).

## Mini-glossaire

- **Mojibake** : texte lisible mais corrompu, produit quand une séquence d'octets encodée dans un format (ex. UTF-8) est réinterprétée avec un autre format (ex. Latin-1) puis affichée ou re-sauvegardée telle quelle.
- **Lockfile** (`uv.lock`, `package-lock.json`) : fichier qui fige les versions exactes de chaque dépendance (et leurs sous-dépendances) résolues à un instant donné — garantit qu'un build reproduit exactement le même résultat sur une autre machine, au lieu de re-résoudre "la dernière version compatible" à chaque fois (qui peut changer entre deux builds).
- **Conteneur jetable** (`docker run --rm ...`) : un conteneur lancé pour une seule commande ponctuelle puis supprimé automatiquement (`--rm`) — utile pour utiliser un outil (ici `uv`, ou `chown` via `alpine`) sans l'installer durablement sur la machine hôte.
- **`DOCKER-USER` / bind `0.0.0.0` vs IP spécifique** : par défaut, Docker publie un port sur toutes les interfaces réseau de la machine (`0.0.0.0`) et manipule directement les règles `iptables` — ce qui peut contourner un pare-feu comme UFW configuré au niveau `INPUT`. Binder explicitement sur une IP précise (ex. `100.68.214.9`, l'IP Tailscale) limite l'écoute à cette seule interface, indépendamment du pare-feu.
