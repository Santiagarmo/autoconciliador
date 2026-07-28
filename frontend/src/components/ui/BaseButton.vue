<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "primary" | "secondary" | "danger" | "ghost";
    type?: "button" | "submit";
    disabled?: boolean;
    loading?: boolean;
  }>(),
  {
    variant: "primary",
    type: "button",
    disabled: false,
    loading: false,
  },
);

const VARIANT_CLASSES: Record<string, string> = {
  primary: "bg-steel text-fg hover:bg-steel-deep",
  secondary: "bg-transparent text-fg ring-1 ring-inset ring-line hover:ring-line-strong hover:bg-surface-sunk",
  danger: "bg-signal-neg text-fg hover:bg-signal-neg/85",
  ghost: "bg-transparent text-fg-muted hover:text-fg underline-offset-4 hover:underline",
};
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    class="inline-flex items-center justify-center gap-2 rounded-sm px-3.5 py-2 font-sans text-[13px] font-medium uppercase tracking-wide transition-[transform,background-color,box-shadow] duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100"
    :class="VARIANT_CLASSES[variant]"
  >
    <svg
      v-if="loading"
      class="h-4 w-4 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
    <slot />
  </button>
</template>
