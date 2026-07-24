import { ref } from "vue";
import { defineStore } from "pinia";

import { pagosApi } from "@/api/pagos.api";
import { extractErrorMessage } from "@/api/http";
import type { PagoDeclaradoCreate, PagoDeclaradoRead } from "@/types/models";

export const usePagosStore = defineStore("pagos", () => {
  const items = ref<PagoDeclaradoRead[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  async function fetchAll(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      items.value = await pagosApi.list();
    } catch (err) {
      error.value = extractErrorMessage(err, "No se pudieron cargar los pagos.");
    } finally {
      isLoading.value = false;
    }
  }

  async function create(payload: PagoDeclaradoCreate): Promise<PagoDeclaradoRead> {
    const pago = await pagosApi.create(payload);
    items.value = [pago, ...items.value];
    return pago;
  }

  return { items, isLoading, error, fetchAll, create };
});
