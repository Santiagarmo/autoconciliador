<script setup lang="ts">
import { computed } from "vue";

import { useCountUp } from "@/composables/useCountUp";

const props = withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    tone?: "neutral" | "brand" | "success" | "danger";
  }>(),
  { tone: "neutral" },
);

const TONE_CLASSES: Record<string, string> = {
  neutral: "text-fg",
  brand: "text-steel",
  success: "text-signal-pos",
  danger: "text-signal-neg",
};

const RULE_CLASSES: Record<string, string> = {
  neutral: "bg-line-strong",
  brand: "bg-steel",
  success: "bg-signal-pos",
  danger: "bg-signal-neg",
};

// El valor casi siempre es numérico (conteos); si llega texto, se muestra tal cual sin animar.
const numericValue = computed(() => (typeof props.value === "number" ? props.value : null));
const animatedValue = useCountUp(computed(() => numericValue.value ?? 0));
</script>

<template>
  <div class="flex flex-col gap-2">
    <p class="font-mono text-label uppercase text-fg-faint">{{ label }}</p>
    <p class="tnum font-display text-stat" :class="TONE_CLASSES[tone]">
      {{ numericValue !== null ? animatedValue : value }}
    </p>
    <span class="h-0.5 w-8 origin-left animate-rule-grow" :class="RULE_CLASSES[tone]" />
  </div>
</template>
