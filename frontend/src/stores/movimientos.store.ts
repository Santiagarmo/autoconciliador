import { ref } from "vue";
import { defineStore } from "pinia";

import { movimientosApi } from "@/api/movimientos.api";
import { extractErrorMessage } from "@/api/http";
import type { MovimientoBancarioRead } from "@/types/models";

export const useMovimientosStore = defineStore("movimientos", () => {
  const items = ref<MovimientoBancarioRead[]>([]);
  const isLoading = ref(false);
  const isIngesting = ref(false);
  const error = ref<string | null>(null);

  async function fetchAll(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      items.value = await movimientosApi.list();
    } catch (err) {
      error.value = extractErrorMessage(err, "No se pudieron cargar los movimientos.");
    } finally {
      isLoading.value = false;
    }
  }

  /** Devuelve el mensaje de aceptación (202); la ingesta real corre en background en el backend. */
  async function ingestar(banco: string, archivo: File): Promise<string> {
    isIngesting.value = true;
    try {
      return await movimientosApi.ingestar(banco, archivo);
    } finally {
      isIngesting.value = false;
    }
  }

  return { items, isLoading, isIngesting, error, fetchAll, ingestar };
});
