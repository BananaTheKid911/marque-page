import { AppShell } from "@/components/layout/AppShell"
import { LibraryPage } from "@/pages/LibraryPage"
import { CURRENTLY_READING } from "@/lib/mock-data"

function App() {
  return (
    <AppShell activeKey="library" currentlyReading={CURRENTLY_READING}>
      <LibraryPage />
    </AppShell>
  )
}

export default App
