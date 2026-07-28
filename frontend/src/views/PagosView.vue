<script setup lang="ts">
import { onMounted, ref } from "vue";

import EstadoBadge from "@/components/features/EstadoBadge.vue";
import PagoForm from "@/components/features/PagoForm.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseModal from "@/components/ui/BaseModal.vue";
import BaseTable, { type TableColumn } from "@/components/ui/BaseTable.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import SpinnerLoader from "@/components/ui/SpinnerLoader.vue";
import { extractErrorMessage } from "@/api/http";
import { usePagosStore } from "@/stores/pagos.store";
import { usePedidosStore } from "@/stores/pedidos.store";
import { useToastStore } from "@/stores/toast.store";
import type { PagoDeclaradoCreate, PagoDeclaradoRead } from "@/types/models";
import { formatCurrency, formatDateTime } from "@/utils/format";

const pagosStore = usePagosStore();
const pedidosStore = usePedidosStore();
const toast = useToastStore();

const isModalOpen = ref(false);
const isSubmitting = ref(false);

const columns: TableColumn<PagoDeclaradoRead>[] = [
  { key: "banco_destino", label: "Banco" },
  { key: "numero_referencia", label: "Referencia" },
  { key: "monto_declarado", label: "Monto", align: "right", render: (row) => formatCurrency(row.monto_declarado) },
  { key: "estado_pago", label: "Estado" },
  { key: "created_at", label: "Registrado", render: (row) => formatDateTime(row.created_at) },
];

function codigoPedido(pedidoId: string): string {
  return pedidosStore.items.find((p) => p.id === pedidoId)?.codigo_pedido ?? pedidoId;
}

async function load(): Promise<void> {
  await Promise.all([pagosStore.fetchAll(), pedidosStore.fetchAll()]);
  if (pagosStore.error) toast.error(pagosStore.error);
}

async function handleCreate(payload: PagoDeclaradoCreate): Promise<void> {
  isSubmitting.value = true;
  try {
    await pagosStore.create(payload);
    toast.success("Pago registrado. Queda a la espera de conciliación.");
    isModalOpen.value = false;
  } catch (err) {
    toast.error(extractErrorMessage(err, "No se pudo registrar el pago."));
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="stagger flex flex-col gap-8">
    <div class="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
      <div>
        <h1 class="font-display text-title text-fg">Pagos declarados</h1>
        <p class="mt-1 font-mono text-xs text-fg-muted">Lo que el asesor registró a partir del comprobante de WhatsApp.</p>
      </div>
      <BaseButton @click="isModalOpen = true">+ Registrar pago</BaseButton>
    </div>

    <Transition name="swap" mode="out-in">
      <SpinnerLoader v-if="pagosStore.isLoading" label="Cargando pagos..." />
      <EmptyState
        v-else-if="pagosStore.items.length === 0"
        title="No hay pagos registrados"
        description="Registra el pago de un pedido usando el número de referencia del comprobante."
      />
      <BaseTable v-else :columns="columns" :rows="pagosStore.items" :row-key="(row) => row.id">
        <template #cell-banco_destino="{ row }">
          <div>
            <p class="font-medium text-fg">{{ row.banco_destino }}</p>
            <p class="font-mono text-xs text-fg-faint">{{ codigoPedido(row.pedido_id) }}</p>
          </div>
        </template>
        <template #cell-estado_pago="{ row }">
          <EstadoBadge kind="pago" :estado="row.estado_pago" />
        </template>
      </BaseTable>
    </Transition>

    <BaseModal :open="isModalOpen" title="Registrar pago" @close="isModalOpen = false">
      <PagoForm :pedidos="pedidosStore.items" :is-submitting="isSubmitting" @submit="handleCreate" />
    </BaseModal>
  </div>
</template>
