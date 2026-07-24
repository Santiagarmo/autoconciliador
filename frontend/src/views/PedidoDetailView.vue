<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import EstadoBadge from "@/components/features/EstadoBadge.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import SpinnerLoader from "@/components/ui/SpinnerLoader.vue";
import { extractErrorMessage } from "@/api/http";
import { useRole } from "@/composables/useRole";
import { usePagosStore } from "@/stores/pagos.store";
import { usePedidosStore } from "@/stores/pedidos.store";
import { useToastStore } from "@/stores/toast.store";
import { EstadoPedido } from "@/types/enums";
import type { PedidoRead } from "@/types/models";
import { formatCurrency, formatDateTime } from "@/utils/format";

const props = defineProps<{ id: string }>();

const pedidosStore = usePedidosStore();
const pagosStore = usePagosStore();
const toast = useToastStore();
const router = useRouter();
const { canDespachar } = useRole();

const pedido = ref<PedidoRead | null>(null);
const isLoading = ref(true);
const isUpdating = ref(false);
const nuevoEstado = ref("");

const RESTRICTED_ESTADOS = new Set<string>([EstadoPedido.LISTO_PARA_DESPACHO, EstadoPedido.DESPACHADO]);

const estadoOptions = computed(() =>
  Object.values(EstadoPedido)
    .filter((estado) => canDespachar.value || !RESTRICTED_ESTADOS.has(estado))
    .map((estado) => ({ value: estado, label: estado })),
);

const pagosDelPedido = computed(() =>
  pagosStore.items.filter((pago) => pago.pedido_id === props.id),
);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    pedido.value = await pedidosStore.fetchOne(props.id);
    nuevoEstado.value = pedido.value.estado_pedido;
    if (pagosStore.items.length === 0) await pagosStore.fetchAll();
  } catch (err) {
    toast.error(extractErrorMessage(err, "No se pudo cargar el pedido."));
    router.push({ name: "dashboard" });
  } finally {
    isLoading.value = false;
  }
}

async function handleUpdateEstado(): Promise<void> {
  if (!pedido.value || nuevoEstado.value === pedido.value.estado_pedido) return;
  isUpdating.value = true;
  try {
    pedido.value = await pedidosStore.update(pedido.value.id, {
      estado_pedido: nuevoEstado.value as EstadoPedido,
    });
    toast.success("Estado del pedido actualizado.");
  } catch (err) {
    toast.error(extractErrorMessage(err, "No se pudo actualizar el estado."));
  } finally {
    isUpdating.value = false;
  }
}

onMounted(load);
</script>

<template>
  <SpinnerLoader v-if="isLoading" label="Cargando pedido..." />

  <div v-else-if="pedido" class="flex flex-col gap-8">
    <div class="flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-6">
      <div>
        <button class="font-mono text-xs text-ink-faint hover:text-ink" @click="router.push({ name: 'dashboard' })">
          ← Volver a pedidos
        </button>
        <h1 class="mt-1 font-display text-2xl text-ink">{{ pedido.codigo_pedido }}</h1>
      </div>
      <EstadoBadge kind="pedido" :estado="pedido.estado_pedido" />
    </div>

    <div class="grid grid-cols-1 divide-y divide-rule border-y border-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
      <div class="py-4 sm:px-6 sm:py-0">
        <p class="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink-faint">Cliente</p>
        <p class="mt-1 text-sm text-ink">{{ pedido.cliente_whatsapp }}</p>
      </div>
      <div class="py-4 sm:px-6 sm:py-0">
        <p class="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink-faint">Monto total</p>
        <p class="tnum mt-1 font-mono text-sm text-ink">{{ formatCurrency(pedido.monto_total) }}</p>
      </div>
      <div class="py-4 sm:px-6 sm:py-0">
        <p class="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink-faint">Creado</p>
        <p class="tnum mt-1 font-mono text-sm text-ink">{{ formatDateTime(pedido.created_at) }}</p>
      </div>
    </div>

    <div>
      <p class="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink-faint">Cambiar estado</p>
      <p class="mt-1 text-xs text-ink-muted">
        Marcar como "Listo para despacho" o "Despachado" requiere rol Auditor.
      </p>
      <div class="mt-4 flex flex-wrap items-end gap-3">
        <div class="w-56">
          <BaseSelect v-model="nuevoEstado" :options="estadoOptions" />
        </div>
        <BaseButton :loading="isUpdating" @click="handleUpdateEstado">Guardar</BaseButton>
      </div>
    </div>

    <div>
      <p class="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink-faint">Pagos declarados</p>
      <ul v-if="pagosDelPedido.length" class="divide-y divide-rule border-y border-rule">
        <li
          v-for="pago in pagosDelPedido"
          :key="pago.id"
          class="flex items-center justify-between py-3"
        >
          <div>
            <p class="text-sm font-medium text-ink">
              {{ pago.banco_destino }} · Ref. {{ pago.numero_referencia }}
            </p>
            <p class="tnum font-mono text-xs text-ink-faint">{{ formatCurrency(pago.monto_declarado) }}</p>
          </div>
          <EstadoBadge kind="pago" :estado="pago.estado_pago" />
        </li>
      </ul>
      <p v-else class="text-sm text-ink-faint">Este pedido aún no tiene pagos declarados.</p>
    </div>
  </div>
</template>
