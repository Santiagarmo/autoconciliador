<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import EstadoBadge from "@/components/features/EstadoBadge.vue";
import PedidoForm from "@/components/features/PedidoForm.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseModal from "@/components/ui/BaseModal.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import BaseTable, { type TableColumn } from "@/components/ui/BaseTable.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import SpinnerLoader from "@/components/ui/SpinnerLoader.vue";
import StatCard from "@/components/ui/StatCard.vue";
import { extractErrorMessage } from "@/api/http";
import { usePedidosStore } from "@/stores/pedidos.store";
import { useToastStore } from "@/stores/toast.store";
import { EstadoPedido } from "@/types/enums";
import type { PedidoCreate, PedidoRead } from "@/types/models";
import { formatCurrency, formatDateTime } from "@/utils/format";

const pedidosStore = usePedidosStore();
const toast = useToastStore();
const router = useRouter();

const isModalOpen = ref(false);
const isSubmitting = ref(false);
const estadoFilter = ref("");

const estadoOptions = [
  { value: "", label: "Todos los estados" },
  ...Object.values(EstadoPedido).map((estado) => ({ value: estado, label: estado })),
];

const filteredPedidos = computed(() =>
  estadoFilter.value
    ? pedidosStore.items.filter((p) => p.estado_pedido === estadoFilter.value)
    : pedidosStore.items,
);

const stats = computed(() => ({
  total: pedidosStore.items.length,
  enAlerta: pedidosStore.items.filter((p) => p.estado_pedido === EstadoPedido.ALERTA_PAGO).length,
  listos: pedidosStore.items.filter((p) => p.estado_pedido === EstadoPedido.LISTO_PARA_DESPACHO).length,
}));

const columns: TableColumn<PedidoRead>[] = [
  { key: "codigo_pedido", label: "Código" },
  { key: "cliente_whatsapp", label: "Cliente" },
  { key: "monto_total", label: "Monto", align: "right", render: (row) => formatCurrency(row.monto_total) },
  { key: "estado_pedido", label: "Estado" },
  { key: "created_at", label: "Creado", render: (row) => formatDateTime(row.created_at) },
];

async function loadPedidos(): Promise<void> {
  await pedidosStore.fetchAll();
  if (pedidosStore.error) toast.error(pedidosStore.error);
}

async function handleCreate(payload: PedidoCreate): Promise<void> {
  isSubmitting.value = true;
  try {
    await pedidosStore.create(payload);
    toast.success(`Pedido ${payload.codigo_pedido} creado.`);
    isModalOpen.value = false;
  } catch (err) {
    toast.error(extractErrorMessage(err, "No se pudo crear el pedido."));
  } finally {
    isSubmitting.value = false;
  }
}

function goToDetail(pedido: PedidoRead): void {
  router.push({ name: "pedido-detail", params: { id: pedido.id } });
}

onMounted(loadPedidos);
</script>

<template>
  <div class="flex flex-col gap-8">
    <div class="flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-6">
      <div>
        <h1 class="font-display text-3xl text-ink">Pedidos</h1>
        <p class="mt-1 font-mono text-xs text-ink-muted">Estado de los pedidos y su verificación de pago.</p>
      </div>
      <BaseButton @click="isModalOpen = true">+ Nuevo pedido</BaseButton>
    </div>

    <div class="stagger grid grid-cols-1 gap-8 border-b border-rule pb-8 sm:grid-cols-3">
      <StatCard label="Total de pedidos" :value="stats.total" tone="brand" />
      <StatCard label="En alerta de pago" :value="stats.enAlerta" tone="danger" />
      <StatCard label="Listos para despacho" :value="stats.listos" tone="success" />
    </div>

    <div class="max-w-xs">
      <BaseSelect v-model="estadoFilter" label="Filtrar por estado" :options="estadoOptions" />
    </div>

    <SpinnerLoader v-if="pedidosStore.isLoading" label="Cargando pedidos..." />
    <EmptyState
      v-else-if="filteredPedidos.length === 0"
      title="No hay pedidos"
      description="Crea el primer pedido para empezar a conciliar pagos."
    />
    <BaseTable
      v-else
      :columns="columns"
      :rows="filteredPedidos"
      :row-key="(row) => row.id"
    >
      <template #cell-estado_pedido="{ row }">
        <EstadoBadge kind="pedido" :estado="row.estado_pedido" />
      </template>
      <template #cell-codigo_pedido="{ row }">
        <button class="font-mono font-medium text-ochre hover:underline" @click="goToDetail(row)">
          {{ row.codigo_pedido }}
        </button>
      </template>
    </BaseTable>

    <BaseModal :open="isModalOpen" title="Nuevo pedido" @close="isModalOpen = false">
      <PedidoForm :is-submitting="isSubmitting" @submit="handleCreate" />
    </BaseModal>
  </div>
</template>
