import { ref } from "vue";
import { defineStore } from "pinia";

export interface Toast {
  id: number;
  message: string;
  variant: "success" | "danger" | "info";
}

let nextId = 0;

/** Estado global de notificaciones efímeras (toasts), consumido por ToastContainer. */
export const useToastStore = defineStore("toast", () => {
  const toasts = ref<Toast[]>([]);

  function push(message: string, variant: Toast["variant"] = "info", timeoutMs = 4000): void {
    const id = nextId++;
    toasts.value.push({ id, message, variant });
    setTimeout(() => dismiss(id), timeoutMs);
  }

  function dismiss(id: number): void {
    toasts.value = toasts.value.filter((t) => t.id !== id);
  }

  return {
    toasts,
    success: (message: string) => push(message, "success"),
    error: (message: string) => push(message, "danger"),
    info: (message: string) => push(message, "info"),
    dismiss,
  };
});
