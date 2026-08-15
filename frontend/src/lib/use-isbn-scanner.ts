import { useCallback, useMemo, useRef } from "react"
import { BrowserMultiFormatReader } from "@zxing/library"

/**
 * Scanner ISBN caméra via zxing (spec §1 : compatible iOS Safari, contrairement
 * à BarcodeDetector). L'appelant fournit l'élément <video> (rendu par
 * IsbnScanPanel) ; le hook ouvre le flux, décode en boucle, et n'accepte un
 * résultat que s'il ressemble à un ISBN (10-13 chiffres).
 *
 * `stop()` (ou le retour de `start`) libère TOUT : boucle de décodage +
 * tracks caméra + srcObject — à appeler au cleanup de l'effet, sinon la
 * caméra reste allumée après l'annulation du scan.
 *
 * LIMITE DÉPLOIEMENT à signaler à Jordy : getUserMedia exige un contexte
 * sécurisé (HTTPS ou localhost). L'app est servie en HTTP pur sur le
 * tailnet (http://100.68.214.9:8123) → la caméra y est refusée par le
 * navigateur. Le scan fonctionnera sur localhost (dev) et exigera un
 * passage en HTTPS (Tailscale HTTPS / `tailscale serve`) pour le mobile.
 * En attendant, l'échec caméra retombe sur l'état "not-detected" et la
 * saisie manuelle d'ISBN reste la voie de repli dessinée par design-ui.
 */
export function useIsbnScanner() {
  const readerRef = useRef<BrowserMultiFormatReader | null>(null)
  const cancelRef = useRef<(() => void) | null>(null)

  const stop = useCallback(() => {
    readerRef.current?.reset()
    readerRef.current = null
    cancelRef.current?.()
    cancelRef.current = null
  }, [])

  const releaseCamera = useCallback((video: HTMLVideoElement) => {
    const stream = video.srcObject as MediaStream | null
    stream?.getTracks().forEach((track) => track.stop())
    video.srcObject = null
  }, [])

  const start = useCallback(
    async (video: HTMLVideoElement, onDetected: (isbn: string) => void) => {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      })
      video.srcObject = stream
      await video.play()

      const reader = new BrowserMultiFormatReader()
      readerRef.current = reader
      let stopped = false

      const stopEverything = () => {
        if (stopped) return
        stopped = true
        reader.reset()
        readerRef.current = null
        releaseCamera(video)
        cancelRef.current = null
      }
      cancelRef.current = stopEverything

      reader.decodeFromVideoElementContinuously(video, (result, _error) => {
        if (stopped || !result) return
        // Un ISBN est un nombre de 10 à 13 chiffres (le "X" de contrôle
        // de l'ISBN-10). Un code-barres inattendu est ignoré : on continue.
        const digits = result.getText().replace(/[^\dXx]/g, "")
        if (digits.length < 10 || digits.length > 13) return
        stopEverything()
        onDetected(digits)
      })

      return stopEverything
    },
    [releaseCamera],
  )

  return useMemo(() => ({ start, stop }), [start, stop])
}
