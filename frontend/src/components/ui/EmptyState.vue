<script setup lang="ts">
withDefaults(defineProps<{ title: string; description?: string }>(), {
  description: "",
});
</script>

<template>
  <div class="flex flex-col items-center gap-2 border-y border-rule py-14 text-center">
    <p class="font-display text-lg text-ink">{{ title }}</p>
    <p v-if="description" class="font-mono text-xs text-ink-faint">{{ description }}</p>
    <slot />
  </div>
</template>
