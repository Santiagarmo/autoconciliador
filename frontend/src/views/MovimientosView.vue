<script setup lang="ts">
import { onMounted, ref } from "vue";

import EstadoBadge from "@/components/features/EstadoBadge.vue";
import IngestaForm from "@/components/features/IngestaForm.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseModal from "@/components/ui/BaseModal.vue";
import BaseTable, { type TableColumn } from "@/components/ui/BaseTable.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import SpinnerLoader from "@/components/ui/SpinnerLoader.vue";
import { extractErrorMessage } from "@/api/http";
import { useMovimientosStore } from "@/stores/movimientos.store";
import { useToastStore } from "@/stores/toast.store";
import type { MovimientoBancarioRead } from "@/types/models";
import { formatCurrency, formatDateTime } from "@/utils/format";

const movimientosStore = useMovimientosStore();
const toast = useToastStore();

const isModalOpen = ref(false);

const columns: TableColumn<MovimientoBancarioRead>[] = [
  { key: "banco_origen", label: "Banco" },
  { key: "fecha_movimiento", label: "Fecha", render: (row) => formatDateTime(row.fecha_movimiento) },
  { key: "monto_real", label: "Monto", align: "right", render: (row) => formatCurrency(row.monto_real) },
  { key: "numero_referencia", label: "Referencia", render: (row) => row.numero_referencia ?? "—" },
  { key: "descripcion_concepto", label: "Concepto" },
  { key: "estado_movimiento", label: "Estado" },
];

async function load(): Promise<void> {
  await movimientosStore.fetchAll();
  if (movimientosStore.error) toast.error(movimientosStore.error);
}

async function handleIngesta(payload: { banco: string; archivo: File }): Promise<void> {
  try {
    const detail = await movimientosStore.ingestar(payload.banco, payload.archivo);
    toast.info(detail);
    isModalOpen.value = false;
  } catch (err) {
    toast.error(extractErrorMessage(err, "No se pudo procesar el extracto."));
  }
}

onMounted(load);
</script>

<template>
  <div class="stagger flex flex-col gap-8">
    <div class="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
      <div>
        <h1 class="font-display text-title text-fg">Movimientos bancarios</h1>
        <p class="mt-1 font-mono text-xs text-fg-muted">Fuente de verdad extraída de los extractos oficiales.</p>
      </div>
      <div class="flex gap-2">
        <BaseButton variant="secondary" @click="load">Refrescar</BaseButton>
        <BaseButton @click="isModalOpen = true">+ Subir extracto</BaseButton>
      </div>
    </div>

    <Transition name="swap" mode="out-in">
      <SpinnerLoader v-if="movimientosStore.isLoading" label="Cargando movimientos..." />
      <EmptyState
        v-else-if="movimientosStore.items.length === 0"
        title="No hay movimientos"
        description="Sube un extracto en PDF para empezar a cruzar pagos."
      />
      <BaseTable v-else :columns="columns" :rows="movimientosStore.items" :row-key="(row) => row.id">
        <template #cell-estado_movimiento="{ row }">
          <EstadoBadge kind="movimiento" :estado="row.estado_movimiento" />
        </template>
      </BaseTable>
    </Transition>

    <BaseModal :open="isModalOpen" title="Subir extracto bancario" @close="isModalOpen = false">
      <IngestaForm :is-submitting="movimientosStore.isIngesting" @submit="handleIngesta" />
    </BaseModal>
  </div>
</template>
