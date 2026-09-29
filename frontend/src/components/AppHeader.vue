<script setup>
/**
 * Carbon UI Shell header. Navigation items switch the active view; the
 * application is small enough that a fixed header is all the chrome we need.
 */
defineProps({
  items: { type: Array, default: () => [] },
  active: { type: String, default: '' },
})

const emit = defineEmits(['navigate'])
</script>

<template>
  <header class="cds--header" aria-label="ArchiGen AI">
    <a class="cds--header__name" href="#generate" @click.prevent="emit('navigate', 'generate')">
      <span class="cds--header__name--prefix">ArchiGen</span>&nbsp;AI
    </a>

    <nav class="cds--header__nav" aria-label="Main navigation">
      <ul class="cds--header__menu-bar">
        <li v-for="item in items" :key="item.id">
          <a
            class="cds--header__menu-item"
            :class="{ 'cds--header__menu-item--current': active === item.id }"
            :href="`#${item.id}`"
            @click.prevent="emit('navigate', item.id)"
          >
            {{ item.label }}
          </a>
        </li>
      </ul>
    </nav>
  </header>
</template>
