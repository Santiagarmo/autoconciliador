<script setup lang="ts">
import { useToastStore } from "@/stores/toast.store";

const toastStore = useToastStore();

const VARIANT_CLASSES: Record<string, string> = {
  success: "border-signal-pos",
  danger: "border-signal-neg",
  info: "border-signal-info",
};
</script>

<template>
  <div class="pointer-events-none fixed inset-x-0 top-4 z-[100] flex flex-col items-center gap-2 px-4">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toastStore.toasts"
        :key="toast.id"
        class="pointer-events-auto flex max-w-sm items-center gap-3 rounded-sm border-l-4 bg-surface-raised px-4 py-3 text-sm text-fg shadow-2xl shadow-black/40"
        :class="VARIANT_CLASSES[toast.variant]"
      >
        <span>{{ toast.message }}</span>
        <button class="text-fg-faint transition-colors hover:text-fg" @click="toastStore.dismiss(toast.id)">✕</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active,
.toast-move {
  transition: all 0.2s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
.toast-leave-active {
  position: absolute;
}
</style>
