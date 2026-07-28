<script setup lang="ts">
defineProps<{ open: boolean; title: string }>();
defineEmits<{ close: [] }>();

const titleId = `modal-title-${Math.random().toString(36).slice(2, 9)}`;
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="modal-scrim fixed inset-0 animate-scrim-in bg-surface/60 backdrop-blur-sm" @click="$emit('close')" />
        <div
          class="modal-panel relative w-full max-w-lg animate-modal-in rounded-sm border-t-2 border-steel bg-surface-raised p-6 shadow-2xl shadow-black/40"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
        >
          <div class="mb-4 flex items-center justify-between">
            <h2 :id="titleId" class="font-display text-subtitle text-fg">{{ title }}</h2>
            <button
              class="rounded-sm p-1 text-fg-faint transition-colors hover:bg-surface-sunk hover:text-fg"
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
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Scrim y panel entran vía animate-scrim-in / animate-modal-in (Tailwind).
   Al salir, el Transition añade estas clases al contenedor raíz; se
   redirige la animación de salida a cada hijo por separado. */
.modal-leave-active .modal-scrim {
  transition: opacity 0.15s ease-in;
}
.modal-leave-active .modal-panel {
  animation: modal-out 0.15s ease-in both;
}
.modal-leave-to .modal-scrim {
  opacity: 0;
}
</style>
