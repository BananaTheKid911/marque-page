# 15/08/2026 — Marque-page : quatre vues supplémentaires et les lacunes qu'elles ont révélées

## Le point de départ

La session précédente avait posé les fondations (Tailwind/shadcn, tokens, shell responsive, Bibliothèque). La suite logique était mécanique : construire les quatre vues qui manquaient — Détail livre, Pile à lire, Wishlist, Réglages — sur le même modèle (données mock, aucun appel réseau).

Ce qui n'était pas prévu, c'est que **regarder ces vues terminées a fait remonter des questions produit** que la spec ne tranchait pas : quel livre affiche-t-on quand plusieurs sont "en cours" en même temps ? Comment classer par thème sans dupliquer les tags ? Comment distinguer un livre acheté d'un livre juste consulté ? Ce document couvre autant ces décisions que le travail visuel qui en a découlé — la spec de données a plus bougé dans cette session que le code lui-même.

---

## 1. Construire d'abord, débattre ensuite

`design-ui` a construit les quatre vues avec le même mandat borné que la session précédente : mocks uniquement, pas de routing réel (une barre "QA" temporaire dans `App.tsx` sert de navigation manuelle entre les écrans, à retirer quand `frontend-dev` branche le vrai routeur). Vérification par capture d'écran réelle aux trois formats (mobile, tablette tactile avec `pointer:coarse` confirmé actif, desktop) — pas de nouvelle méthode ici, la même rigueur que la session d'avant.

C'est en *regardant* ces écrans terminés — pas en les codant — que les questions produit sont apparues. Exemple concret : la carte "En cours" prend le premier livre trouvé avec `status === "reading"` dans le tableau mock (`BOOKS.find(b => b.status === "reading")`). Ça compile, ça s'affiche, rien ne le signale comme un problème — jusqu'à ce qu'on se demande ce qui se passe si deux livres sont "en cours" en même temps. Un bug de logique ne se serait pas caché ; une **question de modèle de données non posée**, si.

---

## 2. Les décisions, une par une

Six points ont été débattus et tranchés avec Jordy, chacun avec un impact différent sur ce qui existe déjà :

**Livre "en cours" principal.** Jordy lit sur plusieurs supports en parallèle (Kindle/KOReader + papier), donc plusieurs livres peuvent être `reading` à la fois. Un seul s'affiche en avant — désigné manuellement, mais **uniquement depuis la page Détail**, pas depuis la grille Bibliothèque. Ce découplage volontaire (l'action existe à un seul endroit, pas deux) a évité de construire une UI de sélection rapide sur la grille qui n'était pas demandée.

**Série.** Concept absent du schéma actuel, inspiré de la table `book.series` de KOReader (`SPEC.md` §4.1). Nom + numéro de tome, décimales autorisées (1.5 pour un hors-série). Contrairement à "livre principal", Jordy a voulu une **vraie surface de navigation** dans la Bibliothèque, pas juste une ligne d'info sur le Détail — un filtre "Série" qui, une fois choisi, change le *comportement* de la grille (tri par tome + badge "T. X" sur la couverture) plutôt que de simplement réduire une liste.

**Format + Possession.** Deux axes orthogonaux qu'aucun champ actuel ne capture : le format (physique/digital/audio, cumulables) et la possession (possédé ou non, **par format** — Jordy peut posséder le papier d'un livre et n'avoir fait qu'emprunter la version numérique). Le mock construit un cas exprès pour prouver que la distinction tient visuellement : un livre avec papier emprunté et digital acheté simultanément.

**Prix + date d'achat.** Un seul champ par livre (pas par format), rempli seulement au moment de l'achat réel — jamais affiché pour un livre en wishlist, où le prix serait "constaté", pas "payé". La distinction évite un champ qui se remplirait à un moment où il n'a pas encore de sens.

**Pile à lire ≠ filtre "à lire".** Le filtre `status = 'tbr'` dans la Bibliothèque existait déjà et affichait le même sous-ensemble de livres que la page "Pile à lire" — un doublon réel, pas apparent. Jordy a tranché : les deux gardent un rôle différent. Le filtre reste un sous-ensemble brut et non ordonné de la collection ; "Pile à lire" devient **"LA SÉLECTION"**, une liste curatée à la main avec un ordre qui compte (priorité de lecture) — rang visible, poignée de réordonnancement (visuelle seulement, la vraie logique de drag revient à `frontend-dev`), note optionnelle par livre.

**Le trou découvert en testant : passer de "à lire" à "en cours".** Aucune des vues construites ne permettait de faire cette transition. En creusant, il est apparu que le statut `reading` doit pouvoir être atteint par **trois chemins différents**, pas un seul : démarrer une session in-app (automatique), un import KOReader qui apporte des sessions pour un livre encore `tbr` (automatique aussi), et une action manuelle explicite — pour les cas où Jordy a déjà commencé un livre ailleurs et veut refléter l'état avant même qu'une session existe côté app. Seul le troisième chemin concernait cette session : un bouton "Marquer comme en cours" (`tbr`) / "Reprendre la lecture" (`on_hold`) a été ajouté à `BookHero.tsx`, en contour, jamais rempli d'encre (`variant="outline"`, l'icône Play est identique à celle du bouton "Démarrer une session" mais sans `fill-current` — même symbole, poids différent).

Cette dernière décision illustre bien la limite de "vérifier par capture d'écran" : une capture montre que ce qui existe fonctionne, elle ne montre pas ce qui *devrait* exister et n'y est pas. Ce trou n'est sorti qu'en réutilisant l'app comme le ferait Jordy, pas en relisant le code des boutons déjà posés.

---

## 3. Un système de badges qui a failli se contredire

Une retouche mineure a manqué de casser une convention déjà posée. Jordy a proposé de mettre le nouveau bouton "Marquer comme en cours" en bordure pointillée. Techniquement trivial (`border-dashed`). Mais `FormatBadges.tsx`, construit dans la même session, utilise déjà le pointillé pour un sens précis : bordure pointillée `--ink-mute` = format **non possédé**, bordure pleine `--ink` = possédé. C'est un vocabulaire visuel spécifique à l'axe *possession*, pas un signifiant générique pour "état pas encore engagé".

Réutiliser le même motif pour un sens différent (ici, "action pas encore prise" sur l'axe *statut de lecture*) aurait créé une ambiguïté silencieuse : le même pointillé sur deux écrans différents, avec deux significations différentes, sans qu'aucune règle écrite ne le documente. `design-ui` a explicitement refusé de trancher seul (conforme au garde-fou d'`AGENTS.md`) et a gardé un contour plein standard, en expliquant le conflit plutôt qu'en l'ignorant.

**Le principe qui en ressort** : dans un design system sans couleur d'accent, chaque levier restant (poids, contour, pointillé, taille) porte plus de charge sémantique qu'il n'en porterait avec de la couleur disponible — un même motif ne peut pas signifier deux choses sur deux écrans du même produit sans devenir bruit.

---

## ✅ Ce qui a été fait

- 4 nouvelles vues : Détail livre, Pile à lire, Wishlist (avec état vide), Réglages — sur mocks, vérifiées par capture d'écran réelle aux 3 formats.
- 6 décisions produit tranchées avec Jordy : livre principal (Détail uniquement), série (vue dédiée Bibliothèque), format + possession (orthogonaux, par format), prix/achat (champ unique, jamais en wishlist), Pile à lire = sélection ordonnée distincte du filtre statut, passage `tbr → reading` par trois chemins (deux automatiques côté backend, un bouton manuel construit ici).
- Bouton "Marquer comme en cours" / "Reprendre la lecture" ajouté à `BookHero.tsx`, icône Play en contour (jamais remplie), cohérent avec la hiérarchie "un seul bouton plein par écran".
- Conflit de vocabulaire visuel (pointillé) identifié et évité avant d'être commité.
- `tsc`, `oxlint`, `npm run build` propres après chaque étape.
- Décisions consignées en mémoire projet (hors du repo Git) pour qu'`OpenCode`/`backend-dev` les retrouve au moment de toucher au schéma — aucun fichier backend modifié durant cette session.

**Non fait, volontairement** : aucune migration de schéma, aucun endpoint, aucune logique de session/import KOReader réelle (ce sont des chemins backend explicitement mis hors périmètre). Pas d'écran de recherche/ajout par ISBN — sujet futur, backend + design. Pas de vraie logique de drag-and-drop sur la Pile à lire.

---

## Prochaine session

1. Revue visuelle groupée dans le navigateur avant tout commit ultérieur — cette session a été validée par capture d'écran automatisée, pas encore par Jordy lui-même en direct.
2. Handoff vers OpenCode : le schéma SQLModel doit intégrer les 6 décisions ci-dessus (série, format/possession, prix/achat, rang de pile à lire, flag livre principal, règle métier des trois déclencheurs de `reading`). `types/book.ts` documente déjà la forme attendue côté front, mais n'est pas le contrat d'API.
3. Écran "Ajouter un livre" (recherche par titre ou ISBN, choix d'édition/couverture) — explicitement repoussé cette session, mais mentionné par Jordy comme besoin réel.
4. Toujours en attente : décision sur `vite-plugin-pwa`, et la question de la couleur de signal reste sans besoin concret identifié (Format/Possession n'en a pas eu besoin, résolu par contour plein/pointillé).

---

## Mini-glossaire

| Terme | Définition |
|---|---|
| **Axe orthogonal** | Deux dimensions qui varient indépendamment l'une de l'autre (ici : format et possession — un livre peut être digital et possédé, digital et non possédé, physique et possédé, etc., les quatre combinaisons ont un sens). Les confondre en un seul champ perd de l'information réelle. |
| **Vocabulaire visuel** | L'ensemble des motifs (contour, poids, espacement) auxquels un design system attribue un sens fixe. Dans un système sans couleur, ce vocabulaire est la seule ressource restante pour distinguer des états — le réutiliser pour un sens différent d'un écran à l'autre le rend ambigu. |
| **Trou de couverture fonctionnelle** | Une capacité que l'utilisateur final attend mais qu'aucune vue construite ne permet — invisible en relisant le code des écrans existants (ils sont corrects pour ce qu'ils couvrent), visible seulement en essayant d'accomplir l'action réelle. |
| **`variant="outline"` vs bouton primaire** | Convention du design system : un seul bouton rempli d'encre par écran (l'action principale), tout le reste en contour — la hiérarchie vient du remplissage, jamais de la couleur. |
