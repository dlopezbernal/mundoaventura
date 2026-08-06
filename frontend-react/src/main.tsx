import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './styles/global.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Service worker: solo en la build de producción. En desarrollo estorba (serviría
// ficheros cacheados por encima del recargado en caliente de Vite). Es lo que hace
// la app INSTALABLE, que es el requisito de entrada del APK — ver public/sw.js y
// docs/APK-ANDROID.md. Si falla el registro no pasa nada: la web funciona igual.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js').catch(() => {
      /* sin service worker la app sigue funcionando; solo no será instalable */
    })
  })
}
