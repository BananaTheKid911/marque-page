@AGENTS.md

## Claude Code — spécifique

`AGENTS.md` (importé ci-dessus) fait autorité sur le design system, les layouts, l'architecture et les règles réseau. Il est partagé avec OpenCode : le corriger là-bas, **jamais dupliquer son contenu ici**.

### Répartition des outils

| Travail | Outil | Modèle |
|---|---|---|
| Design system, composants visuels, layouts, Tailwind/shadcn, accessibilité, PWA côté apparence | **Claude Code**, sous-agent `design-ui` | Sonnet 5 |
| Backend Python — SQLModel, Alembic, API FastAPI, parsers KOReader, intégrations Open Library/Google Books, pytest, Docker | OpenCode, agent `backend-dev` | deepseek-v4-flash |
| Frontend React — état, routing, client API, formulaires, zxing, service worker | OpenCode, agent `frontend-dev` | deepseek-v4-flash |

**Le gate design traverse les deux outils.** Une tâche visuelle qui arrive côté OpenCode doit être renvoyée ici, pas implémentée là-bas. Inversement, `design-ui` ne touche pas à la logique métier ni aux routes.

Différence avec Feader, qui utilise le même pattern : là-bas le design était déjà figé (maquette React exhaustive), le gate garantissait la fidélité de traduction. **Ici le design est en cours de création** — `design-ui` a donc un vrai pouvoir de décision, borné par les tokens d'`AGENTS.md`.

### Journal de session — obligatoire en fin de session

Toute session qui a produit quelque chose se clôt par une entrée dans **`docs/journal/`**, à la racine de ce repo, au format `AAAA-MM-JJ-slug.md`. Le journal d'un projet vit dans le repo de ce projet — `homelab-mn56/docs/journal/` reste réservé aux sessions d'infrastructure.

Le lecteur visé est Jordy, qui apprend le développement et l'AI engineering, et qui réutilisera ces notes pour un site de documentation. Le journal n'est donc pas un changelog : **il explique pourquoi, pas seulement quoi**.

Structure :

1. `# JJ/MM/AAAA — Marque-page : sujet en une phrase`
2. **Le point de départ** — la question réellement posée, et ce qu'elle a révélé.
3. Sections numérotées, chacune expliquant un mécanisme, pas un diff. Les commandes réelles avec leur sortie réelle. Les concepts nouveaux définis au passage.
4. **✅ Ce qui a été fait** — liste à puces.
5. **Prochaine session** — étapes numérotées.
6. **Mini-glossaire** — tableau terme/définition.

Deux règles de fond : documenter les échecs et les impasses au même titre que les réussites, puisque c'est là qu'est l'apprentissage ; et distinguer explicitement ce qui a été **vérifié par exécution** de ce qui est supposé.

### État du repo

- **Phase 0 faite et vérifiée** (09/08/2026, commit `1edd579`) : monorepo `backend/` + `frontend/`, Dockerfile multi-stage, compose bindé Tailscale. Le conteneur `marquepage` tourne, healthcheck vert, `/api/v1/health` répond.
- **Phases 1 à 6 : rien.** `backend/app/main.py` contient un health check et le service des fichiers statiques, c'est tout. Pas de modèle, pas de migration, pas d'endpoint métier.
- `frontend/` est le scaffold Vite brut. **Tailwind, shadcn et `vite-plugin-pwa` ne sont pas installés.**
- `package-lock.json` est bien présent et committé — le `npm ci` du Dockerfile passe.
- `SPEC.md` est fiable sur les §1 à §5 et §8. Les §0, §6, §7, §9 et §10 ont été corrigés le 14/08/2026 et portent un avertissement : **ne pas suivre une instruction Synology qui aurait survécu quelque part.**

### Pièges connus

- `.env.example` existe, mais `APP_PASSWORD` et `SESSION_GAP_SEC` **ne sont pas branchées** dans le compose : l'app ne les lit pas encore. Les câbler en Phase 1, au moment où le code s'en sert — ajouter un `env_file:` pointant vers un `.env` absent ferait échouer `docker compose up` sur un service qui tourne actuellement très bien.
- Pas de `sudo` interactif configuré sur le MN56. Pour tout ce qui exige root — corriger un ownership après un build, générer un lockfile — passer par un conteneur jetable, comme en Phase 0.
- Le repo **n'a pas de remote Git**. Un seul commit local.
