import { createApp } from 'vue'

// IBM Carbon Design System v11 — compiled stylesheet (includes the
// `.cds--white`, `.cds--g10`, `.cds--g90` and `.cds--g100` theme zones).
import '@carbon/styles/css/styles.css'
import './styles/app.css'

import App from './App.vue'

createApp(App).mount('#app')
