<script setup lang="ts">
defineProps<{ open: boolean; title: string }>();
defineEmits<{ close: [] }>();
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="fixed inset-0 bg-ink/30 backdrop-blur-sm" @click="$emit('close')" />
      <div class="relative w-full max-w-lg border-t-2 border-ochre bg-paper-raised p-6 shadow-xl">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="font-display text-lg font-medium text-ink">{{ title }}</h2>
          <button
            class="rounded-sm p-1 text-ink-faint hover:bg-paper-sunk hover:text-ink"
            aria-label="Cerrar"
            @click="$emit('close')"
          >
            <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path
                fill-rule="evenodd"
                d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
                clip-rule="evenodd"
              />
            </svg>
          </button>
        </div>
        <slot />
      </div>
    </div>
  </Teleport>
</template>
