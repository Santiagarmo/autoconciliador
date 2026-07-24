import { ref } from "vue";
import { defineStore } from "pinia";

import { conciliacionesApi } from "@/api/conciliaciones.api";
import { extractErrorMessage } from "@/api/http";
import type { ConciliacionRead } from "@/types/models";

export const useConciliacionesStore = defineStore("conciliaciones", () => {
  const items = ref<ConciliacionRead[]>([]);
  const isLoading = ref(false);
  const isRunning = ref(false);
  const error = ref<string | null>(null);

  async function fetchAll(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      items.value = await conciliacionesApi.list();
    } catch (err) {
      error.value = extractErrorMessage(err, "No se pudieron cargar las conciliaciones.");
    } finally {
      isLoading.value = false;
    }
  }

  /** Restringido a AUDITOR; devuelve el conteo de conciliados para feedback inmediato. */
  async function run(): Promise<number> {
    isRunning.value = true;
    try {
      const summary = await conciliacionesApi.run();
      await fetchAll();
      return summary.conciliados;
    } finally {
      isRunning.value = false;
    }
  }

  return { items, isLoading, isRunning, error, fetchAll, run };
});
