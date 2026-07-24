<script setup lang="ts">
import { onMounted } from "vue";

import EstadoBadge from "@/components/features/EstadoBadge.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseTable, { type TableColumn } from "@/components/ui/BaseTable.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import SpinnerLoader from "@/components/ui/SpinnerLoader.vue";
import { extractErrorMessage } from "@/api/http";
import { useRole } from "@/composables/useRole";
import { useConciliacionesStore } from "@/stores/conciliaciones.store";
import { useToastStore } from "@/stores/toast.store";
import type { ConciliacionRead } from "@/types/models";
import { formatDateTime } from "@/utils/format";

const conciliacionesStore = useConciliacionesStore();
const toast = useToastStore();
const { canRunReconciliation } = useRole();

const columns: TableColumn<ConciliacionRead>[] = [
  { key: "pago_declarado_id", label: "Pago declarado" },
  { key: "movimiento_bancario_id", label: "Movimiento bancario" },
  { key: "tipo_conciliacion", label: "Tipo" },
  { key: "created_at", label: "Fecha", render: (row) => formatDateTime(row.created_at) },
];

async function load(): Promise<void> {
  await conciliacionesStore.fetchAll();
  if (conciliacionesStore.error) toast.error(conciliacionesStore.error);
}

async function handleRun(): Promise<void> {
  try {
    const conciliados = await conciliacionesStore.run();
    toast.success(`Conciliación ejecutada: ${conciliados} pago(s) conciliado(s).`);
  } catch (err) {
    toast.error(extractErrorMessage(err, "No se pudo ejecutar la conciliación."));
  }
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-8">
    <div class="flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-6">
      <div>
        <h1 class="font-display text-3xl text-ink">Conciliaciones</h1>
        <p class="mt-1 font-mono text-xs text-ink-muted">Cruce entre pagos declarados y movimientos bancarios.</p>
      </div>
      <div class="flex gap-2">
        <BaseButton variant="secondary" @click="load">Refrescar</BaseButton>
        <BaseButton
          v-if="canRunReconciliation"
          :loading="conciliacionesStore.isRunning"
          @click="handleRun"
        >
          Ejecutar conciliación
        </BaseButton>
      </div>
    </div>

    <p v-if="!canRunReconciliation" class="border-l-2 border-indigo-slate bg-indigo-slate/5 px-3 py-2 font-mono text-xs text-ink-muted">
      Solo el rol Auditor puede ejecutar el motor de conciliación manualmente.
    </p>

    <SpinnerLoader v-if="conciliacionesStore.isLoading" label="Cargando conciliaciones..." />
    <EmptyState
      v-else-if="conciliacionesStore.items.length === 0"
      title="Aún no hay conciliaciones"
      description="Registra pagos, sube extractos y ejecuta el cruce para verlas aquí."
    />
    <BaseTable v-else :columns="columns" :rows="conciliacionesStore.items" :row-key="(row) => row.id">
      <template #cell-tipo_conciliacion="{ row }">
        <EstadoBadge kind="conciliacion" :estado="row.tipo_conciliacion" />
      </template>
    </BaseTable>
  </div>
</template>
