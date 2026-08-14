# 14/08/2026 — Marque-page : décision du design system et câblage des agents

## Le point de départ

La question posée était simple : « on a vérifié que Feader était complet et bien orchestré pour l'implémentation sur OpenCode, fais pareil pour Marque-page ». Sous-entendu : appliquer la même grille de vérification, trouver les mêmes trous.

Elle a révélé deux choses très différentes. Le **code** de la Phase 0 était sain — le conteneur tournait depuis quatre jours, healthcheck vert. L'**orchestration**, elle, n'existait pas du tout : aucun des quatre éléments câblés sur Feader n'était présent ici. Et en creusant, un problème plus vicieux que l'absence de configuration : une spécification qui donnait des instructions périmées avec autorité.

---

## 1. La grille de vérification, et ce qu'elle a trouvé

Sur Feader, quatre choses rendent un repo « prêt pour les agents » :

1. un fichier de contexte racine (`AGENTS.md`) que tous les outils lisent ;
2. un `CLAUDE.md` qui l'importe, parce que Claude Code ne lit jamais `AGENTS.md` ;
3. des agents projet dans les bons dossiers de découverte ;
4. une source de vérité assainie, sans instructions contradictoires.

Marque-page n'en avait aucun. Le diagnostic exact :

```
marque-page/
├── SPEC.md          ← 432 lignes, mais partiellement périmé
├── backend/         ← health check seul
├── frontend/        ← scaffold Vite brut
├── Dockerfile
├── docker-compose.yml
└── .gitignore
```

Pas de `AGENTS.md`, pas de `CLAUDE.md`, pas de `.opencode/agent/`, pas de `.claude/agents/`, pas de `docs/journal/`, pas de remote Git.

Un point positif quand même, qui contraste avec Feader : `package-lock.json` est présent et committé, donc le `npm ci` du Dockerfile passe. Sur Feader, ce fichier manquant rendait le build impossible.

### Vérifier l'état réel plutôt que le supposer

Avant de conclure quoi que ce soit, on a interrogé la machine :

```bash
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
```

```
feader-api      Up 29 hours (healthy)   100.68.214.9:3001->3001/tcp
gametracker     Up 4 days (healthy)     100.68.214.9:4000->4000/tcp
marquepage      Up 4 days (healthy)     100.68.214.9:8123->8000/tcp
portainer       Up 4 days               100.68.214.9:9443->9443/tcp
```

```bash
curl -s http://100.68.214.9:8123/api/v1/health
# {"status":"ok"}
```

Ce que ça apprend : le mot « healthy » ne vient pas de nulle part. Le `healthcheck:` du compose exécute une commande à intervalle régulier *à l'intérieur* du conteneur ; tant qu'elle renvoie 0, Docker marque le service sain. Le nôtre appelle `/api/v1/health` en Python. C'est donc Docker qui teste l'app en continu, pas nous une fois.

---

## 2. Le vrai piège : une spec qui a l'air fiable

`SPEC.md` cible le Synology DS218+. Pas en passant — dans le détail, avec autorité :

| Ce que dit SPEC.md | Ce que fait le code réel |
|---|---|
| §0 : `PUID=1026`, `PGID=100`, `/volume1/docker/` « à respecter à l'identique » | aucun PUID, volumes sous `/home/banserv/docker/marquepage/` |
| §7 : Dockerfile complet avec `ENV PUID=1026 PGID=100`, `node:20-slim` | `node:24-slim`, pas de PUID |
| §7 : `ports: "8123:8000"`, « derrière ton reverse proxy » | `100.68.214.9:8123:8000`, pas de proxy |
| §9 : « Héberger sur NAS Docker » listé comme besoin couvert | le NAS est du stockage pur depuis P2/P3 |

Le danger n'est pas qu'un humain se trompe — Jordy sait que le NAS ne fait plus tourner de service. Le danger est qu'un **agent** lise le §7 pour modifier le déploiement et régresse le bind Tailscale en remettant `"8123:8000"`, ce qui exposerait le port sur toutes les interfaces.

C'est le troisième repo du projet où le même motif apparaît. La leçon est devenue une règle : **toujours vérifier la cible de déploiement d'une spec avant de la suivre.**

### La découverte annexe : la palette LPA n'existe plus

Le §6 disait « réutilise ta palette LPA » et proposait un or `#c8a96e` avec Cormorant Garamond. Vérification faite dans le repo LPA :

```bash
grep -rn --include='*.md' -iE '(--accent|Cormorant|#[0-9a-f]{6})' ~/projects/lpa
```

`lpa/AGENTS.md` définit aujourd'hui `--accent: #051229` (bleu marine), fond blanc, Inter + Instrument Sans. L'or et le serif ne survivent que dans `.opencode/config-draft-original.md`, un brouillon.

Autrement dit la spec citait un état de LPA qui n'existait plus. Quatrième élément périmé.

Ça a changé la nature de la discussion design : l'argument n'était plus « cohérence avec LPA » (LPA est un site d'affiliation, Marque-page une app perso — la cohérence entre les deux n'a aucune valeur), mais la seule question utile : **est-ce que cette palette sert des couvertures de livres ?**

---

## 3. La décision design

Trois directions ont été maquettées sur le **même écran, avec les mêmes couvertures**, seules les variables de thème changeant. C'est le point méthodologique important : comparer deux palettes sur deux contenus différents ne prouve rien. Les couvertures choisies étaient volontairement hétérogènes — une crème, une rouge saturée, une blanche, une vert sombre — parce qu'une vraie bibliothèque ne s'accorde pas à une palette.

Les trois : le sombre or/serif du §6, les tokens exacts de Feader, et un chrome achromatique.

**Aucune n'a été retenue.** Jordy a demandé l'inverse du postulat de départ : fond clair, presque sépia, pour l'effet liseuse. Direction finale :

- papier `#f6efe3` (sépia clair, choisi parmi trois tons proposés en direct dans la maquette) ;
- encre `#1b1611` — un noir **légèrement chaud**, pas un `#000` pur, qui creuserait un trou sur du papier sépia ;
- **aucune couleur d'accent** ;
- une seule famille typographique, un serif de lecture façon Bookerly.

### La contrainte que « pas d'accent » impose

Sans couleur, il ne reste que trois leviers de hiérarchie : la masse noire du bouton principal (seule zone sombre de l'écran, donc point de fixation naturel), le poids et la taille du texte, et le filet sous l'élément actif. C'est écrit tel quel dans `AGENTS.md` pour que l'agent design ne parte pas inventer un token à la première difficulté.

Une décision explicitement **différée** : les écrans sans couverture (réglages, wishlist vide, import KOReader) sont là où le monochrome sera le plus exposé. La consigne donnée à l'agent est de remonter la question plutôt que de trancher — le noir sait dire « actif », il ne sait pas dire « attention ».

### Bookerly ne peut pas être embarquée

Bookerly appartient à Amazon et n'est pas distribuable. Les substituts retenus sont **Charis SIL** (dérivé de Charter, dont Bookerly descend) et **Literata**, tous deux sous licence libre — à auto-héberger dans l'image, jamais servis depuis un CDN de polices, ce qui fuiterait l'IP du lecteur à chaque chargement et contredirait la logique tailnet du homelab.

La pile déclarée commence quand même par `"Bookerly"` : si elle est installée localement sur la machine du lecteur, elle sort ; personne d'autre n'est affecté.

---

## 4. Les layouts, et le raisonnement sur la tablette

Trois formats demandés : téléphone, tablette MagicPad 2 en paysage, desktop.

### Vérifier le matériel avant de dessiner

La MagicPad 2 était supposée en 2800 × 1840. Vérification faite : elle est en **3000 × 1920** OLED, ratio ≈ 14:9 (2800 × 1840 est la définition de la Huawei MatePad 12 X). À DPR 2, ça donne un viewport CSS d'environ **1500 × 960 px** en paysage.

Ce chiffre n'est pas décoratif, il commande le layout : en 14:9, **la hauteur est la ressource rare et la largeur est abondante**. Une barre de nav horizontale coûterait ~8 % de la hauteur utile pour afficher quatre mots. D'où le choix de déplacer la nav dans un **rail vertical** — on paie la nav dans la dimension où on est riche.

### Le problème que la décision « desktop inchangé » a créé

Le rail se déclenchait à « largeur ≥ 1200 px ». Mais Jordy a validé que le desktop garde sa barre du haut — or le desktop est large lui aussi. **La largeur ne suffisait plus à distinguer les deux cas.**

Le discriminant retenu est `@media (pointer: coarse)` : tablette = doigt, desktop = souris. C'est exactement la différence sémantique entre les deux situations, et ça justifie au passage les cibles tactiles de 44 px.

Deux effets de bord, documentés parce qu'ils surprendront sinon : brancher un clavier-trackpad sur la MagicPad peut basculer le pointeur en `fine` et ramener la barre du haut (ce qui se défend — on a retrouvé un curseur) ; un portable à écran tactile hériterait du rail. Aucun ne casse quoi que ce soit, les deux layouts étant complets.

### Requêtes de conteneur plutôt que de fenêtre

Les trois compositions sortent d'un seul jeu de règles, en `@container` et non `@media`. Un composant décide alors de sa forme d'après **la place qu'on lui donne**, pas d'après la taille de la fenêtre. Deux bénéfices concrets : la maquette peut afficher les trois formats côte à côte sur une seule page (ce qui prouve que les breakpoints fonctionnent, au lieu de le promettre), et rien ne cassera si un panneau change de largeur plus tard.

Limite honnête de la maquette : la condition `pointer: coarse` ne peut pas être simulée depuis une souris. Elle y est donc représentée par une classe `.touch`, et le fichier le dit en commentaire pour que personne ne recopie la classe en production.

---

## 5. Le câblage

Trois agents créés, répartis selon la frontière logique/visuel :

| Agent | Outil | Fichier | Modèle |
|---|---|---|---|
| `backend-dev` | OpenCode | `.opencode/agent/backend-dev.md` | `deepseek-v4-flash`, temp 0.2 |
| `frontend-dev` | OpenCode | `.opencode/agent/frontend-dev.md` | `deepseek-v4-flash`, temp 0.2 |
| `design-ui` | Claude Code | `.claude/agents/design-ui.md` | `sonnet` (épinglé) |

**Pourquoi pas les agents globaux** que le §10 de la spec suggérait par leur nom (`python-dev`, `css-ui`) : ils existent bien, mais leur lecture montre qu'ils sont écrits pour le stack affi-build. `python-dev` parle scrapers, ETL et exports GSC ; `css-ui` parle overrides GeneratePress et `site-config.yml`. Les activer ici reviendrait à donner à un agent un périmètre sans rapport avec la tâche.

**Le gate design traverse les deux outils** : `frontend-dev` doit s'arrêter sur toute tâche visuelle et renvoyer vers Claude Code. Nuance par rapport à Feader, où le même pattern existe : là-bas le design était déjà figé et le gate garantissait la fidélité de traduction ; ici le design est en cours de création, donc `design-ui` a un vrai pouvoir de décision, borné par les tokens.

**`CLAUDE.md` importe `AGENTS.md`** par un `@AGENTS.md` en première ligne. Claude Code ne lit jamais `AGENTS.md` de lui-même ; l'import évite de dupliquer le contenu, donc évite deux sources qui divergent.

### Vérification par exécution, pas par présence du fichier

La leçon de Feader : un fichier d'agent bien écrit au mauvais endroit est de la documentation, pas de la configuration. On vérifie donc que l'outil les voit vraiment :

```bash
cd ~/projects/marque-page && opencode agent list
```

```
backend-dev (all)
frontend-dev (all)
chef-de-projet (all)
css-ui (all)
...
```

Les deux agents projet apparaissent aux côtés des globaux. Découverte confirmée.

Pour `design-ui`, Claude Code charge les définitions d'agents **au démarrage de la session** : il ne sera disponible qu'à la prochaine session, pas dans celle qui vient de le créer.

### `.env.example` sans câblage du compose

`APP_PASSWORD` et `SESSION_GAP_SEC` sont documentées, mais volontairement **pas** ajoutées au `docker-compose.yml`. Raison : un `env_file:` qui pointe vers un `.env` absent fait échouer `docker compose up`. Le conteneur tourne actuellement très bien et l'application ne lit pas encore ces variables — les brancher maintenant, c'est prendre un risque pour zéro bénéfice. À faire en Phase 1, quand le code s'en servira.

---

## ✅ Ce qui a été fait

- Diagnostic complet du repo face à la grille de vérification Feader.
- `SPEC.md` corrigé : §0, §6, §7, §9 et §10 réécrits pour la cible MN56, avec un avertissement en tête de document. Les §1 à §5 et §8 (schéma, intégrations, algorithme KOReader, API, phases) n'ont pas été touchés — ils restent la spécification de vérité.
- Design system décidé et documenté : papier `#f6efe3`, encre `#1b1611`, sans accent, serif de lecture.
- Trois layouts définis avec leurs points de rupture, dont un layout paysage spécifique à la MagicPad 2.
- `AGENTS.md` créé (contexte, tokens, layouts, réseau, données, garde-fous).
- `CLAUDE.md` créé avec `@AGENTS.md`, répartition des outils, règles de journal.
- Trois agents créés, découverte OpenCode vérifiée par `opencode agent list`.
- `.env.example` créé.

**Non fait, volontairement :** aucun commit, aucun remote Git créé, compose non modifié.

---

## Prochaine session

1. Committer ce lot et créer le remote GitHub privé (le repo n'a qu'un commit local et aucun remote).
2. Déplacer `homelab-mn56/docs/journal/2026-08-09-p4-marque-page-scaffold-phase0.md` vers ce repo, pour respecter la convention « le journal d'un projet vit dans le repo du projet ».
3. Attaquer la **Phase 1** avec `backend-dev` : ajouter SQLModel et Alembic au `pyproject.toml`, générer le modèle conforme au DDL du §2, la première migration, puis l'endpoint `/lookup`.
4. Installer Tailwind, shadcn et `vite-plugin-pwa` côté `frontend/` — préalable à toute Phase 2.
5. Mettre à jour le statut de la tâche Notion (page `3b71221c1008818c80fee727154ede4c`).

---

## Mini-glossaire

| Terme | Définition |
|---|---|
| **Requête de conteneur** (`@container`) | Règle CSS qui s'applique selon la largeur de l'élément parent déclaré conteneur, et non de la fenêtre. Permet à un composant d'être responsive à sa place réelle. |
| **`pointer: coarse`** | Requête média décrivant le dispositif de pointage principal. `coarse` = doigt (imprécis), `fine` = souris ou stylet. Sert à distinguer tactile et bureau sans se fier à la largeur. |
| **DPR** (device pixel ratio) | Rapport entre pixels physiques et pixels CSS. Un écran 3000 px à DPR 2 se comporte en CSS comme un écran de 1500 px. |
| **Gate design** | Règle d'organisation : un agent doit s'arrêter sur une catégorie de tâche et la renvoyer à un autre agent ou outil, au lieu de la traiter. |
| **Frontmatter YAML** | Bloc de métadonnées entre `---` en tête d'un fichier Markdown. Sans lui, un fichier d'agent n'est pas reconnu comme agent par l'outil. |
| **Healthcheck Docker** | Commande exécutée périodiquement dans le conteneur ; son code de retour détermine l'état `healthy` / `unhealthy` affiché par `docker ps`. |
| **WAL** (Write-Ahead Logging) | Mode journal de SQLite où les écritures vont d'abord dans un fichier `-wal` séparé. Permet lectures et écriture simultanées. Conséquence : `.db`, `.db-wal` et `.db-shm` forment un tout indissociable pour un backup. |
| **Partial md5** | Empreinte calculée sur des extraits d'un fichier plutôt que sur sa totalité. Rapide, mais deux fichiers différents peuvent la partager — d'où la confirmation manuelle du matching KOReader. |
| **Hotlink** | Afficher une image en pointant l'URL d'un serveur tiers au lieu de l'héberger. Révèle l'IP du lecteur au tiers et casse si la source disparaît. |
| **OFL** (SIL Open Font License) | Licence libre permettant redistribution et intégration d'une police, y compris auto-hébergée. |
| **`env_file`** | Directive Compose qui charge des variables depuis un fichier. Si le fichier est absent, le démarrage échoue — d'où la prudence à le déclarer avant d'en avoir besoin. |
