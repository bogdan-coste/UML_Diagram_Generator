import { ref, watchEffect } from 'vue'

/**
 * Carbon themes that ship with `@carbon/styles`. Each maps to a zone class
 * (`.cds--white`, `.cds--g10`, `.cds--g90`, `.cds--g100`) applied to <html>.
 */
export const THEMES = [
  { id: 'white', label: 'White' },
  { id: 'g10', label: 'Gray 10' },
  { id: 'g90', label: 'Gray 90' },
  { id: 'g100', label: 'Gray 100' },
]

const STORAGE_KEY = 'archigen.theme'
const DEFAULT_THEME = 'white'

function readStoredTheme() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return THEMES.some((t) => t.id === stored) ? stored : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

const theme = ref(readStoredTheme())

function applyTheme(id) {
  const root = document.documentElement
  THEMES.forEach((t) => root.classList.remove(`cds--${t.id}`))
  root.classList.add(`cds--${id}`)
  root.dataset.carbonTheme = id
  root.style.colorScheme = id === 'g90' || id === 'g100' ? 'dark' : 'light'
  try {
    window.localStorage.setItem(STORAGE_KEY, id)
  } catch {
    // localStorage unavailable (private mode); theme just won't persist.
  }
}

// watchEffect runs immediately, so the theme is applied on first import.
watchEffect(() => applyTheme(theme.value))

export function useTheme() {
  function setTheme(id) {
    if (THEMES.some((t) => t.id === id)) theme.value = id
  }

  return { theme, themes: THEMES, setTheme }
}
