<script setup lang="ts">
import type { BadgeVariant } from "@/types/enums";

withDefaults(defineProps<{ label: string; variant?: BadgeVariant }>(), {
  variant: "neutral",
});

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: "bg-paper-sunk text-ink-muted border-rule-strong",
  info: "bg-indigo-slate/10 text-indigo-slate border-indigo-slate",
  success: "bg-moss/10 text-moss border-moss",
  warning: "bg-amber-deep/10 text-amber-deep border-amber-deep",
  danger: "bg-oxide/10 text-oxide border-oxide",
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
