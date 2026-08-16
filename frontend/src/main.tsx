import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import "./index.css"
import App from "./App.tsx"
import { BooksProvider } from "@/context/books"
import { registerSW } from "virtual:pwa-register"

// Service worker PWA (vite-plugin-pwa, registerType: autoUpdate).
// `immediate: true` : le SW installé prend le contrôle dès l'enregistrement,
// sans attendre un second chargement — comportement voulu pour une app
// self-hosted mono-utilisateur (une seule version active à tout moment).
registerSW({ immediate: true })

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <BooksProvider>
        <App />
      </BooksProvider>
    </BrowserRouter>
  </StrictMode>,
)
