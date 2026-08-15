# Marque-page — Référence agents

Application de suivi de lecture auto-hébergée : bibliothèque personnelle, sessions de lecture chronométrées, highlights, et l'intégration **KOReader** comme vrai différenciant.

Ce fichier est le contexte partagé de tous les agents, OpenCode comme Claude Code. **Le lire avant d'agir.**

---

## Sources de vérité — qui fait foi sur quoi

| Sujet | Source |
|---|---|
| Schéma de données, API REST, algorithme KOReader, intégrations métadonnées, plan de build | `SPEC.md` §1 à §5 et §8 |
| **Design system, layouts, points de rupture** | **ce fichier** (le §6 de `SPEC.md` est périmé et le dit) |
| Déploiement réel | `Dockerfile` et `docker-compose.yml` à la racine — les fichiers font foi, `SPEC.md` §7 les décrit |
| Répartition des agents | `SPEC.md` §10 + ce fichier |

`SPEC.md` a été écrite pour un déploiement sur le NAS Synology, avant la décision « NAS = stockage pur, MN56 = compute Docker ». Les sections concernées ont été corrigées le 14/08/2026 et portent un avertissement. **Si une instruction de `SPEC.md` parle de `/volume1/`, de `PUID`/`PGID`, de reverse proxy ou d'un design sombre à accent or : elle est morte, ne pas l'appliquer.**

---

## Contexte projet

**Utilisateur :** Jordy — consultant SEO, autodidacte technique, self-hoster. Lit sur **Kindle + KOReader** et en **papier**. Apprend en faisant : expliquer le *pourquoi* d'un choix, brièvement, avant le *comment*.

**Infra :** MN56 (Ubuntu Server 24.04) + Docker + Tailscale. Le NAS Synology est du stockage pur, il n'héberge plus de service. Accès exclusivement via le tailnet, **aucun port public**.

**Appareils cibles :** téléphone Android, tablette **Honor MagicPad 2 12,3"** (3000 × 1920, ratio ≈ 14:9 — soit ≈ 1500 × 960 px CSS en paysage), desktop Fedora.

---

## Stack (imposé, cf. `SPEC.md` §1)

- **Backend** : Python 3.12 + FastAPI + SQLModel + Uvicorn, migrations Alembic, tests pytest.
- **Base** : SQLite en mode WAL, fichier unique, mono-utilisateur.
- **Frontend** : React + Vite + TypeScript + TailwindCSS + shadcn/ui, build statique servi par le backend.
- **Conteneur** : image unique multi-stage (build front → runtime `python:3.12-slim`), un seul process.

Versions réellement installées en Phase 0 : React 19.2.8, Vite 8.2.1, TypeScript 6.0.2 (scaffoldées par `npm create vite`, pas choisies à la main). **Tailwind, shadcn et `vite-plugin-pwa` ne sont pas encore installés** — `frontend/package.json` ne contient que `react` et `react-dom`. Les ajouter est le premier geste de la Phase 2.

---

## Design system

Direction validée le 14/08/2026 : **papier clair, encre noire, aucune couleur d'accent.** L'app doit évoquer une liseuse, pas un tableau de bord. La couleur de l'écran vient exclusivement des couvertures de livres — c'est pour ça que le chrome n'en a aucune.

### Tokens

```css
:root {
  /* surfaces */
  --paper:    #f6efe3;  /* fond principal — sépia clair de liseuse */
  --card:     #fcf7ee;  /* cartes flottantes, barres de nav */
  --line:     #e2d8c6;  /* bordures */
  --line-2:   #ece3d4;  /* séparateurs internes, plus discrets */

  /* encre */
  --ink:      #1b1611;  /* texte principal + états actifs */
  --ink-soft: #4a4034;  /* texte secondaire */
  --ink-mute: #7a6f5f;  /* labels, métadonnées, nav inactive */
}
```

**Pas de token `--accent`. C'est volontaire, ne pas en inventer un.** L'encre `#1b1611` est un noir légèrement chaud : sur du papier sépia, un `#000` pur creuse un trou. Ne pas la « corriger » vers du noir pur.

### Hiérarchie sans couleur

En l'absence d'accent, trois leviers seulement :

1. **La masse noire.** Le bouton d'action principal est rempli d'encre — c'est la seule zone sombre de l'écran, donc le point de fixation naturel. Un seul par écran.
2. **Le poids et la taille.** Un chiffre de progression à 34 px n'a besoin d'aucune couleur pour dominer.
3. **Le filet sous l'élément actif.** Nav et onglets : `border-bottom` en `--ink`, jamais de pastille colorée.

### Typographie

Une seule famille, un serif de lecture. **Bookerly est la référence esthétique mais appartient à Amazon et n'est pas distribuable** — ne jamais l'embarquer. Les substituts libres à retenir, tous deux sous licence OFL et conçus pour la lecture écran :

- **Charis SIL** — dérivé de Charter, dont Bookerly descend. Le plus proche.
- **Literata** — dessinée pour Google Play Livres, un peu plus large.

À **auto-héberger dans l'image Docker**, jamais servie depuis un CDN de polices : ça fuiterait l'IP du lecteur à chaque page et contredirait la logique tailnet de tout le homelab. Le choix final entre les deux reste à trancher au moment de l'intégration — vérifier la licence exacte de la version téléchargée à ce moment-là plutôt que de se fier à cette note.

Pile CSS à déclarer :

```css
--serif: "Bookerly", "Charis SIL", "Literata", "Charter",
         "Iowan Old Style", Georgia, serif;
```

`Bookerly` en tête est intentionnel : si l'utilisateur l'a installée localement, il la verra ; personne d'autre n'est affecté.

### Échelle typographique

| Rôle | Taille | Notes |
|---|---|---|
| Titre de livre en détail | 21 px | `text-wrap: balance` |
| Titre de section | 19–22 px | 22 px en paysage large |
| Chiffre de progression | 34 px | `font-variant-numeric: tabular-nums` |
| Nav, corps, boutons | 15 px | |
| Titre de livre en grille | 14 px | |
| Auteur, sessions | 12–13,5 px | |
| Labels en capitales | 10–11 px | `letter-spacing: 0.16em` |

Tout ce qui aligne des chiffres en colonne — durées, pages, dates — prend `tabular-nums`.

### Formes

- Rayons **faibles** : 2 px sur les couvertures, 3 px sur les boutons, 4 px sur les cartes. Le papier ne fait pas de gros arrondis.
- Ombres **chaudes et diffuses**, jamais grises : `rgba(60, 46, 26, …)`.
- Les couvertures sont les héros : ratio 2/3 strict, ombre portée marquée, aucune bordure.
- **Rien ne colle à rien.** Pas de barre de nav à fond plein soudée au contenu par un filet : c'est l'espace qui sépare. Le panneau latéral est une carte détachée qui flotte au-dessus du papier.

---

## Layouts

Les trois compositions sortent d'**un seul jeu de règles**, en **requêtes de conteneur** (`@container`) et non de fenêtre — un composant décide de sa forme d'après la place qu'on lui donne, ce qui évite de tout casser si un panneau change de largeur plus tard.

| Condition | Nav | Grille | Livre en cours |
|---|---|---|---|
| `< 700` | Barre basse, 5 entrées | 3 colonnes fixes | Bandeau en tête de bibliothèque |
| `≥ 700` | Liens en haut | `auto-fill`, min 118 px | Carte latérale 280 px |
| `≥ 1200` **et** `pointer: coarse` | Rail vertical 176 px | `auto-fill`, min 132 px | Carte latérale 300 px |

**Pourquoi le rail est réservé au tactile.** En paysage 14:9, la hauteur est la ressource rare et la largeur est gratuite : déplacer la nav sur le côté rend ~8 % de hauteur utile. Mais le desktop est large lui aussi et **garde sa barre du haut** (décision du 14/08). La largeur ne suffit donc pas à distinguer les deux cas — le discriminant est `@media (pointer: coarse)`, qui distingue le doigt du curseur et justifie au passage les cibles tactiles.

Effets de bord connus, aucun ne casse quoi que ce soit puisque les deux layouts sont complets : brancher un clavier-trackpad sur la MagicPad peut basculer le pointeur en `fine` (retour à la barre du haut, ce qui se défend puisqu'on retrouve un curseur) ; un portable tactile hériterait du rail.

**Règles transverses :**
- **Seule la grille défile.** Rail, carte latérale et barre basse restent fixes — perdre sa nav au scroll est le défaut le plus pénible en paysage court.
- Le bandeau « Reprendre » du mobile et la carte « En cours » du desktop sont **le même composant**, pas deux écrans à maintenir : mêmes données, deux formes selon la place.
- Cibles tactiles **≥ 44 px** sur la barre basse et le rail.
- Ordre de la barre basse : Bibliothèque · Pile à lire · **Ajouter** (pastille d'encre au centre) · Stats · Réglages.

### Décisions actées

**Carte/bandeau « En cours » sans livre primaire désigné** (décidé le 15/08/2026) : ne pas la masquer. Afficher un état vide invitant à choisir — message du type « Aucun livre en cours — choisis-en un dans ta pile à lire » avec un lien vers la PAL. C'est un écran sans couverture de plus à dessiner (cf. ci-dessous), pas un cas particulier.

### Ce qui n'est pas encore dessiné

Les écrans **sans couverture** — réglages, wishlist vide, import KOReader, rattachement manuel d'un livre KOReader, et désormais l'état vide de la carte « En cours ». C'est là que l'absence d'accent se verra, et c'est là qu'on décidera s'il faut une **couleur de signal** (une seule, réservée aux états : erreur d'import, livre abandonné). Le noir sait dire « actif », il ne sait pas dire « attention ». **Ne pas trancher seul :** remonter la question à Jordy quand un de ces écrans arrive.

---

## Réseau — la règle exacte

- Côté **hôte** (`ports:` du `docker-compose.yml`) : `100.68.214.9:8123:8000`. Jamais `0.0.0.0` (exposition publique), jamais `127.0.0.1` (le téléphone et la tablette perdraient l'accès via le tailnet).
- Côté **conteneur** (`--host` d'uvicorn) : `0.0.0.0` est correct et doit le rester. Dans un conteneur, écouter sur `0.0.0.0` est nécessaire pour que le mapping fonctionne — l'isolation vient de l'hôte.

Ne jamais confondre les deux niveaux. Port `8123` sur l'hôte ; `3001` est pris par feader-api, `4000` par gametracker, `3000` par OpenChamber, `9443` par Portainer.

---

## Données et sécurité

- La base SQLite et les couvertures vivent sur le **NVMe local du MN56** (`/home/banserv/docker/marquepage/`), **non couvert par le backup 3-2-1** qui ne protège que le NAS. Tant que ce n'est pas résolu, considérer la base comme perdable et garder l'export JSON (`GET /export`, §5) comme filet.
- **Jamais de hotlink de couverture** : télécharger l'image localement et la servir depuis `covers/`. C'est explicite au §3 de la spec, pour la vie privée et la résilience.
- Tous les appels aux APIs externes (Open Library, Google Books) partent du **backend**, jamais du front.
- `APP_PASSWORD` via variable d'environnement uniquement. Jamais en dur, jamais loggé.
- Ne jamais committer `.env`, `data/`, `covers/`, `node_modules/`, `*.db`.

---

## Garde-fous

- **Ne pas committer sauf demande explicite** de Jordy.
- Une phase à la fois, validée sur ses critères d'acceptation (`SPEC.md` §8) avant d'attaquer la suivante.
- Fournir le **code complet** d'un fichier modifié — jamais de `// ... reste du code`.
- Ne jamais supposer qu'un comportement fonctionne parce que le code a l'air correct : distinguer explicitement ce qui a été **vérifié par exécution** de ce qui est supposé.
- Anti scope-creep : devant un « et si on ajoutait aussi… », poser la question — *qu'est-ce qui casse vraiment dans le flow actuel ?* Si rien, on n'ajoute pas.
