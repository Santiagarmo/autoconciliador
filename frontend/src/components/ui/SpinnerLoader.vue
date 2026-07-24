<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), { label: "Cargando..." });
</script>

<template>
  <div class="flex items-center justify-center gap-2 py-14 font-mono text-xs uppercase tracking-widest text-ink-faint">
    <span class="flex gap-1">
      <span class="h-1 w-1 animate-pulse rounded-full bg-ochre [animation-delay:0ms]" />
      <span class="h-1 w-1 animate-pulse rounded-full bg-ochre [animation-delay:200ms]" />
      <span class="h-1 w-1 animate-pulse rounded-full bg-ochre [animation-delay:400ms]" />
    </span>
    <span>{{ label }}</span>
  </div>
</template>
