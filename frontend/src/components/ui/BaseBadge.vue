<script setup lang="ts">
import type { BadgeVariant } from "@/types/enums";

withDefaults(defineProps<{ label: string; variant?: BadgeVariant }>(), {
  variant: "neutral",
});

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: "bg-surface-sunk text-fg-muted border-line-strong",
  info: "bg-signal-info/10 text-signal-info border-signal-info",
  success: "bg-signal-pos/10 text-signal-pos border-signal-pos",
  warning: "bg-signal-warn/10 text-signal-warn border-signal-warn",
  danger: "bg-signal-neg/10 text-signal-neg border-signal-neg",
};
</script>

<template>
  <span
    class="inline-flex items-center rounded-sm border-l-2 px-2 py-1 font-mono text-[11px] font-medium uppercase tracking-wider"
    :class="VARIANT_CLASSES[variant]"
  >
    {{ label }}
  </span>
</template>
