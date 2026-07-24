<script setup lang="ts">
import { RouterLink } from "vue-router";

const NAV_ITEMS = [
  { to: "/", label: "Pedidos", index: "01", icon: "M4 6h16M4 12h16M4 18h7" },
  { to: "/pagos", label: "Pagos", index: "02", icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V6m0 10v2" },
  { to: "/movimientos", label: "Movimientos", index: "03", icon: "M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2", },
  { to: "/conciliaciones", label: "Conciliaciones", index: "04", icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" },
];
</script>

<template>
  <aside class="hidden w-60 shrink-0 flex-col border-r border-rule bg-paper lg:flex">
    <div class="flex h-16 items-center gap-2 px-5">
      <span class="font-mono text-xs text-ochre">AC/</span>
      <span class="font-display text-base font-medium tracking-tight text-ink">AutoConciliador</span>
    </div>
    <nav class="flex flex-1 flex-col gap-0.5 px-3 py-2">
      <RouterLink
        v-for="item in NAV_ITEMS"
        :key="item.to"
        :to="item.to"
        class="flex items-center gap-3 border-l-2 border-transparent px-3 py-2.5 font-mono text-[13px] uppercase tracking-wide text-ink-muted hover:text-ink"
        active-class="border-ochre text-ochre hover:text-ochre"
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
          <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
        </svg>
        <span class="text-ink-faint">{{ item.index }}</span>
        {{ item.label }}
      </RouterLink>
    </nav>
  </aside>
</template>
