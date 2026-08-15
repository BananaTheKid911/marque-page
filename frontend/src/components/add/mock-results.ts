import type { SearchCandidate } from "./types"

/**
 * Résultats factices pour dessiner les états de l'écran "Ajouter un livre"
 * sans backend de recherche branché (aucun endpoint de recherche ISBN /
 * titre-auteur n'existe encore côté API — hors périmètre design-ui).
 *
 * TODO frontend-dev : supprimer ce fichier et `runMockSearch` dans
 * AddBookPage.tsx au profit du vrai client (contrat à définir avec
 * backend-dev — probablement GET /search?isbn=… et GET /search?q=…,
 * agrégeant Open Library + Google Books côté serveur comme pour les
 * couvertures déjà téléchargées ailleurs dans l'app).
 *
 * Déclencheurs de démo (aucun rapport avec une future validation réelle) :
 * une requête contenant "erreur" simule une panne réseau, "zzz" ou une
 * requête vide simule "aucun résultat", tout le reste renvoie 3 candidats.
 */
export function mockResultsFor(query: string): SearchCandidate[] {
  const seed = query.trim() || "roman"
  const title = capitalize(seed)

  return [
    {
      id: "ol-1",
      title: seed.length > 3 ? title : "La Horde du Contrevent",
      subtitle: null,
      authors: ["Alain Damasio"],
      publisher: "La Volte",
      publishedDate: "2004",
      isbn: "9782845631319",
      source: "openlibrary",
      covers: [
        { id: "ol-1-c1", source: "openlibrary", label: "Édition La Volte, 2004", hasImage: true },
        { id: "ol-1-c2", source: "openlibrary", label: "Édition poche, 2006", hasImage: true },
      ],
    },
    {
      id: "gb-1",
      title,
      subtitle: "Édition augmentée",
      authors: ["Alain Damasio"],
      publisher: "Gallimard",
      publishedDate: "2020",
      isbn: "9782072899918",
      source: "google_books",
      covers: [
        { id: "gb-1-c1", source: "google_books", label: "Couverture Google Books", hasImage: true },
        { id: "gb-1-c2", source: "openlibrary", label: "Scan alternatif Open Library", hasImage: false },
      ],
    },
    {
      id: "ol-2",
      title: `${title} — tome 1`,
      subtitle: null,
      authors: ["Alain Damasio", "Collectif"],
      publisher: null,
      publishedDate: null,
      isbn: null,
      source: "openlibrary",
      covers: [
        { id: "ol-2-c1", source: "openlibrary", label: "Sans couverture répertoriée", hasImage: false },
      ],
    },
  ]
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}
