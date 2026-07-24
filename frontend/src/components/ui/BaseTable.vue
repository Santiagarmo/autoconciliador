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
  <div class="overflow-x-auto border-t border-rule">
    <table class="min-w-full text-sm">
      <thead class="bg-paper-sunk">
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            class="whitespace-nowrap px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink-faint"
            :class="col.align === 'right' ? 'text-right' : 'text-left'"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-rule">
        <tr v-for="row in rows" :key="rowKey(row)" class="transition-colors hover:bg-ochre-tint/60">
          <td
            v-for="col in columns"
            :key="col.key"
            class="whitespace-nowrap px-4 py-3 text-ink"
            :class="col.align === 'right' ? 'text-right' : 'text-left'"
          >
            <slot :name="`cell-${col.key}`" :row="row">
              {{ col.render ? col.render(row) : (row as Record<string, unknown>)[col.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
