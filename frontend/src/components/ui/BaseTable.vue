<script setup lang="ts" generic="T extends Record<string, unknown>">
/**
 * Tabla genérica orientada a config: cada vista declara sus `columns` en
 * lugar de duplicar `<table>`/`<tr>` por cada recurso (pedidos, pagos,
 * movimientos, conciliaciones). Una celda puede usar `render` para
 * formateo simple, o el slot `cell-<key>` para markup custom (badges, links).
 */
export interface TableColumn<T> {
  key: string;
  label: string;
  render?: (row: T) => string;
  align?: "left" | "right";
}

defineProps<{
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
}>();
</script>

<template>
  <div class="overflow-x-auto rounded-sm border-t border-line">
    <table class="min-w-full text-sm">
      <thead class="bg-surface-raised">
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            class="whitespace-nowrap px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint"
            :class="col.align === 'right' ? 'text-right' : 'text-left'"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <TransitionGroup tag="tbody" name="row" class="divide-y divide-line">
        <tr
          v-for="row in rows"
          :key="rowKey(row)"
          class="border-l-2 border-l-transparent transition-colors hover:border-l-steel hover:bg-steel-tint"
        >
          <td
            v-for="col in columns"
            :key="col.key"
            class="whitespace-nowrap px-4 py-3 text-fg"
            :class="col.align === 'right' ? 'text-right' : 'text-left'"
          >
            <slot :name="`cell-${col.key}`" :row="row">
              {{ col.render ? col.render(row) : (row as Record<string, unknown>)[col.key] }}
            </slot>
          </td>
        </tr>
      </TransitionGroup>
    </table>
  </div>
</template>

<style scoped>
/* Entrada escalonada acotada a las primeras 8 filas — evita que una tabla
   larga tarde segundos en terminar de aparecer. Filas más allá de la 8
   entran juntas, sin delay adicional. */
.row-enter-active {
  animation: row-in 0.22s ease-out both;
}
.row-enter-active:nth-child(1) { animation-delay: 0ms; }
.row-enter-active:nth-child(2) { animation-delay: 25ms; }
.row-enter-active:nth-child(3) { animation-delay: 50ms; }
.row-enter-active:nth-child(4) { animation-delay: 75ms; }
.row-enter-active:nth-child(5) { animation-delay: 100ms; }
.row-enter-active:nth-child(6) { animation-delay: 125ms; }
.row-enter-active:nth-child(7) { animation-delay: 150ms; }
.row-enter-active:nth-child(8) { animation-delay: 175ms; }
.row-leave-active {
  transition: opacity 0.15s ease-in;
}
.row-leave-to {
  opacity: 0;
}
.row-move {
  transition: transform 0.2s ease;
}
</style>
