# 15/08/2026 — Marque-page : fondations du design system et un bug de container query auto-référente

## Le point de départ

La question posée était directe : « continue, on n'a pas fait les phases design ». Le constat de `CLAUDE.md` était sans appel — quatre phases backend committées (modèle de données, taxonomie, sessions, highlights), et côté `frontend/` rien d'autre que le scaffold brut de `npm create vite`. Aucun Tailwind, aucun shadcn, aucune police, aucun composant.

En parallèle, une question annexe est arrivée sur la Phase 5 KOReader (backend, hors périmètre de cette session) : l'unité de `duration` dans `statistics.sqlite3` (secondes ou millisecondes selon la version) et le sort des highlights KOReader (sidecars `.sdr/metadata.epub.lua`, format Lua non documenté). Les deux ont été arbitrés en cinq minutes avec `AskUserQuestion` — auto-calibration de la durée via `book.total_read_time` plutôt que d'attendre un fichier réel, et report des highlights en Phase 6 puisque les critères d'acceptation de la Phase 5 ne portent que sur les sessions. Rien à documenter de plus ici, c'est un aiguillage, pas un mécanisme.

Le vrai sujet de cette session est ailleurs : le sous-agent `design-ui` a posé des fondations propres du premier coup, mais un bug invisible au code review s'est révélé seulement à l'écran — et sa cause est une limitation CSS peu connue qui mérite d'être comprise, pas juste corrigée.

---

## 1. Le bootstrap, délégué et vérifié

Le sous-agent `design-ui` (Sonnet, `.claude/agents/design-ui.md`) a reçu un mandat volontairement borné : poser Tailwind CSS v4 + shadcn/ui, câbler les tokens d'`AGENTS.md` en variables CSS, auto-héberger une police serif, construire le shell responsive en `@container`, et livrer une vue Bibliothèque sur données mock — sans toucher à l'API, au routing ni au state, réservés à `frontend-dev` (OpenCode) dans une passe ultérieure.

Résultat vérifié par build, pas seulement lu :

```bash
npm run build
```

```
dist/assets/index-CwGyBGzc.css   41.80 kB │ gzip:   8.32 kB
✓ built in 243ms
```

Le CSS compilé contenait bien les bonnes valeurs :

```css
:root{--paper:#f6efe3;--ink:#1b1611; ... }
.aspect-\[2\/3\]{aspect-ratio:2/3}
```

Ce point compte pour la suite : le build de production était **prouvé correct** avant même la première capture d'écran. Ça a évité de chercher le bug au mauvais endroit plus tard.

### La police, sous contrainte de licence réelle

`AGENTS.md` laissait le choix entre Charis SIL et Literata « à trancher au moment de l'intégration ». L'agent a choisi **Literata**, téléchargée depuis le dépôt officiel `google/fonts` (licence OFL 1.1 vérifiée et copiée dans `public/fonts/OFL.txt`, pas supposée), convertie TTF → WOFF2 via `fonttools`. Zéro CDN de polices, conforme à la règle réseau tailnet.

---

## 2. Le faux positif : Dark Reader

Première capture d'écran envoyée par Jordy : fond marron foncé partout, alors que le CSS compilé disait sans ambiguïté `--paper: #f6efe3` (clair). Plutôt que de modifier du CSS à l'aveugle, le diagnostic s'est fait par élimination :

- Le build de prod prouvait déjà que le code source était correct.
- Le motif visuel — un fond clair devenu sombre **en conservant sa teinte chaude** — est la signature typique d'une extension de thème/mode sombre forcé, pas d'un bug CSS (un vrai bug de tokens produirait des couleurs incohérentes, pas une palette inversée mais cohérente).

Confirmé en une question : navigation privée (désactive les extensions) → couleurs correctes. C'était Dark Reader.

**La leçon utile pour la suite** : avant de modifier du code face à un rendu visuel suspect, vérifier d'abord ce qui est *prouvé* correct (ici, le CSS compilé) avant de suspecter le reste. Un ajout resté en place malgré tout, parce qu'il ne coûte rien et aide dans le cas général : `<meta name="color-scheme" content="light">` dans `index.html` — certains mécanismes de dark mode forcé le respectent, contrairement à la seule propriété CSS `color-scheme`.

---

## 3. Le vrai bug : une container query qui se cible elle-même

Une fois Dark Reader écarté, deux symptômes concrets restaient sur la vraie capture (couleurs correctes) : un vide à droite du nav avant le bord de l'écran, et une grille de couvertures qui s'affichait comme des barres plates sans texte ni ombre.

### Pourquoi il a fallu un vrai navigateur, pas la lecture du code

Le CSS source était lu et relu sans trouver l'anomalie — chaque règle, prise isolément, est correcte. Le seul moyen de trancher était d'observer le DOM calculé par un vrai moteur de rendu. Playwright était déjà installé mais son Chromium ne se lançait pas :

```
error while loading shared libraries: libatk-1.0.so.0: cannot open shared object file
```

Sans `sudo` sur cette machine (piège déjà documenté dans `CLAUDE.md`), la solution a été de télécharger les paquets `.deb` des dépendances manquantes et de les **extraire sans les installer** :

```bash
apt-get download libatk1.0-0t64 libatk-bridge2.0-0t64 libcairo2 ...
dpkg-deb -x libatk1.0-0t64_*.deb extracted/
export LD_LIBRARY_PATH="$PWD/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
```

`apt-get download` récupère le `.deb` sans droits root (il écrit dans le répertoire courant, pas dans le système). `dpkg-deb -x` extrait son contenu dans un dossier arbitraire, toujours sans root. `LD_LIBRARY_PATH` dit au programme où chercher ses bibliothèques dynamiques en plus des emplacements système. Une dizaine d'allers-retours (chaque lib manquante en révèle une autre) plus tard, Chromium headless tournait et une vraie capture d'écran est sortie :

```bash
chrome --headless=new --no-sandbox --window-size=1440,900 \
  --screenshot=screen.png http://localhost:5183/
```

### Le diagnostic, obtenu par injection de script plutôt que par relecture

La capture confirmait le bug (carte "En cours" et grille inversées par rapport à ce que le CSS déclarait) mais pas sa cause. Plutôt que de continuer à deviner, un petit script temporaire injecté dans `index.html` a écrit l'état réel du DOM dans le `<title>` de la page (récupérable via `--dump-dom` sans avoir besoin du protocole DevTools) :

```js
document.title = "cols=" + getComputedStyle(shell).gridTemplateColumns
               + " areas=" + getComputedStyle(shell).gridTemplateAreas;
```

Résultat :

```
areas="topnav" "main" "bottomnav"    ← le template MOBILE (1 colonne), à 1440px de large !
cols=1164.64px 0px 275.359px         ← 3 pistes au lieu des 2 attendues
```

Le `.shell` restait bloqué sur sa grille par défaut (mobile), **quelle que soit la largeur réelle**. Les colonnes 700px et 1200px n'avaient jamais été appliquées.

### Le mécanisme exact

`.shell` portait à la fois :

```css
.shell {
  container-type: inline-size;   /* le rend "conteneur de requête" */
  grid-template-columns: 1fr;    /* et il se définit lui-même en dessous */
}
@container (min-width: 700px) {
  .shell { grid-template-columns: 280px minmax(0, 1fr); }  /* se re-cible lui-même */
}
```

C'est une **container query auto-référente**. La spec CSS l'interdit explicitement pour les propriétés qui affectent la taille : un élément ne peut pas changer son propre agencement sur la base d'une requête portant sur sa propre taille, sous peine de dépendance circulaire (la taille déterminerait le style, qui déterminerait la taille…). La règle n'est donc **jamais appliquée à l'élément qui établit le conteneur, seulement à ses descendants**.

Ce qui explique le symptôme composite observé : `.shell__topnav { display: flex }` s'appliquait bien (c'est un *descendant* de `.shell`, donc légitime), mais `.shell { grid-template-columns }` ne s'appliquait jamais (c'est `.shell` qui se cible *lui-même*). D'où le mélange incohérent — nav qui passe en mode "liens en haut" mais grille jamais mise à jour, carte latérale livrée à un placement automatique du navigateur dans une colonne fantôme.

### Le correctif

Séparer les deux rôles sur deux éléments : un `.shell-frame` externe porte `container-type`, un `.shell` interne (son enfant direct) porte la grille pilotée par `@container`. `.shell` devient un *descendant* du conteneur, plus l'élément qui se requête lui-même — la même règle s'applique alors normalement.

```tsx
<div className="shell-frame">
  <div className="shell bg-paper">
    {/* nav, sidebar, main, bottomnav — inchangés */}
  </div>
</div>
```

Reconstruit et recapturé à 1440px et 390px : sidebar à gauche, grille pleine largeur à droite, nav flush au coin, 18 couvertures en 2:3 avec titre/auteur ; en mobile, bandeau + grille 3 colonnes + barre basse. Les deux bugs — nav tronqué et grille écrasée — venaient de la même cause unique.

---

## ✅ Ce qui a été fait

- Tailwind CSS v4 + shadcn/ui installés et configurés dans `frontend/`.
- Tokens d'`AGENTS.md` déclarés en variables CSS (`--paper`, `--ink`, etc.), aucun `--accent` inventé.
- Police Literata auto-hébergée, licence OFL vérifiée et versionnée (`public/fonts/OFL.txt`).
- Shell responsive en `@container` (barre basse mobile / nav haut / rail tactile ≥1200px + `pointer:coarse`).
- Vue Bibliothèque (grille de couvertures 2/3, filtres statut/auteur/genre/tag) sur données mock typées.
- Bug de container query auto-référente trouvé et corrigé (`.shell-frame` / `.shell` séparés), vérifié par capture d'écran réelle à deux largeurs.
- Chromium headless rendu utilisable sans `sudo` sur cette machine (dépendances extraites via `apt-get download` + `dpkg-deb -x`, réutilisable pour de futures vérifications visuelles).
- Commit `31764b8` : fondations design + vue Bibliothèque.

**Non fait, volontairement** : branchement API réel (routing, state, appels `/api/v1/*`) — réservé à `frontend-dev`. `vite-plugin-pwa` pas installé. Décision de la couleur de signal (statuts "Abandonné"/destructive) non tranchée, comme prévu par `AGENTS.md`.

---

## Prochaine session

1. Continuer les vues design : Détail livre, Pile à lire, Wishlist, Réglages — ce dernier étant un des écrans « sans couverture » qui posera la question de la couleur de signal.
2. Trancher (avec Jordy, sur cas réel) si une couleur de signal unique est introduite pour les états abandonné/erreur, ou si le traitement typographique pur suffit à l'usage.
3. Passer la main à `frontend-dev` (OpenCode) pour brancher les vues déjà construites sur les vrais endpoints (`/books`, `/authors`, `/labels`) à la place des données mock.
4. Installer `vite-plugin-pwa` (préalable Phase 6, mais autant le faire pendant qu'on est dans `frontend/`).
5. Réutiliser le dossier de libs extraites (`/tmp/.../localdeps/extracted`) si une vérification visuelle est de nouveau nécessaire — éviter de re-télécharger les mêmes paquets.

---

## Mini-glossaire

| Terme | Définition |
|---|---|
| **Container query auto-référente** | Une règle `@container` qui tente de restyler l'élément qui établit le contexte de requête lui-même, plutôt qu'un de ses descendants. Interdit par la spec CSS pour les propriétés affectant la taille — la règle ne s'applique alors jamais silencieusement, sans erreur visible. |
| **`container-type: inline-size`** | Propriété qui transforme un élément en conteneur de requête, permettant à ses *descendants* de réagir à sa largeur via `@container`. |
| **`apt-get download`** | Télécharge un paquet `.deb` dans le répertoire courant sans l'installer et sans droits root. |
| **`dpkg-deb -x`** | Extrait le contenu d'un `.deb` vers un dossier arbitraire, sans l'installer sur le système. |
| **`LD_LIBRARY_PATH`** | Variable d'environnement listant des dossiers supplémentaires où le système cherche les bibliothèques partagées (`.so`) au lancement d'un programme. |
| **`getComputedStyle`** | API JavaScript qui renvoie la valeur *réellement appliquée* d'une propriété CSS après résolution de toutes les règles — la seule façon fiable de vérifier ce qu'un navigateur applique vraiment, par opposition à ce que le code source déclare. |
| **`--dump-dom`** | Flag Chromium headless qui affiche le DOM final (après exécution JS) sur la sortie standard, sans interface graphique. |
| **OFL** (SIL Open Font License) | Licence libre autorisant la redistribution et l'auto-hébergement d'une police. |
| **Faux positif de diagnostic** | Une piste plausible (ici, un bug CSS) qui se révèle être causée par autre chose (une extension navigateur). Le distinguer tôt — via ce qui est déjà prouvé correct — évite de corriger du code qui n'était pas en cause. |
