<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    tone?: "neutral" | "brand" | "success" | "danger";
  }>(),
  { tone: "neutral" },
);

const TONE_CLASSES: Record<string, string> = {
  neutral: "text-ink",
  brand: "text-ochre",
  success: "text-moss",
  danger: "text-oxide",
};

const RULE_CLASSES: Record<string, string> = {
  neutral: "bg-rule-strong",
  brand: "bg-ochre",
  success: "bg-moss",
  danger: "bg-oxide",
};
</script>

<template>
  <div class="flex flex-col gap-2">
    <p class="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink-faint">{{ label }}</p>
    <p class="tnum font-display text-3xl font-medium" :class="TONE_CLASSES[tone]">{{ value }}</p>
    <span class="h-0.5 w-8" :class="RULE_CLASSES[tone]" />
  </div>
</template>
