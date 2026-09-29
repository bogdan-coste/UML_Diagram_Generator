<script setup>
import { computed } from 'vue'
import { Checkmark20, Error20, Information20, WarningAlt20 } from '@carbon/icons-vue'

const props = defineProps({
  /** @type {'info' | 'success' | 'warning' | 'error'} */
  kind: { type: String, default: 'info' },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  lowContrast: { type: Boolean, default: false },
})

const ICONS = { success: Checkmark20, warning: WarningAlt20, error: Error20, info: Information20 }

const icon = computed(() => ICONS[props.kind] ?? Information20)
const role = computed(() => (props.kind === 'error' ? 'alert' : 'status'))
</script>

<template>
  <div
    class="cds--inline-notification app-notification"
    :class="[
      `cds--inline-notification--${kind}`,
      { 'cds--inline-notification--low-contrast': lowContrast },
    ]"
    :role="role"
  >
    <div class="cds--inline-notification__details">
      <component :is="icon" class="cds--inline-notification__icon" />
      <div class="cds--inline-notification__text-wrapper">
        <p v-if="title" class="cds--inline-notification__title">{{ title }}</p>
        <div v-if="subtitle" class="cds--inline-notification__subtitle">{{ subtitle }}</div>
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-notification {
  inline-size: 100%;
  max-inline-size: none;
  margin-block-end: 1.5rem;
}
</style>
