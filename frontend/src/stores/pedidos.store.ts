import { ref } from "vue";
import { defineStore } from "pinia";

import { pedidosApi } from "@/api/pedidos.api";
import { extractErrorMessage } from "@/api/http";
import type { EstadoPedido } from "@/types/enums";
import type { PedidoCreate, PedidoRead, PedidoUpdate } from "@/types/models";

export const usePedidosStore = defineStore("pedidos", () => {
  const items = ref<PedidoRead[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  async function fetchAll(estado?: EstadoPedido): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      items.value = await pedidosApi.list(estado);
    } catch (err) {
      error.value = extractErrorMessage(err, "No se pudieron cargar los pedidos.");
    } finally {
      isLoading.value = false;
    }
  }

  async function create(payload: PedidoCreate): Promise<PedidoRead> {
    const pedido = await pedidosApi.create(payload);
    items.value = [pedido, ...items.value];
    return pedido;
  }

  async function update(id: string, payload: PedidoUpdate): Promise<PedidoRead> {
    const pedido = await pedidosApi.update(id, payload);
    const index = items.value.findIndex((p) => p.id === id);
    if (index !== -1) items.value[index] = pedido;
    return pedido;
  }

  async function fetchOne(id: string): Promise<PedidoRead> {
    return pedidosApi.get(id);
  }

  return { items, isLoading, error, fetchAll, fetchOne, create, update };
});
