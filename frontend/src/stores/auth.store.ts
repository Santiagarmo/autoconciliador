import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { authApi } from "@/api/auth.api";
import { extractErrorMessage, getStoredToken, registerUnauthorizedHandler, setStoredToken } from "@/api/http";
import { RolUsuario } from "@/types/enums";
import type { UserRead } from "@/types/models";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(getStoredToken());
  const user = ref<UserRead | null>(null);
  const isHydrating = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => Boolean(token.value));
  // El rol se deriva del usuario cargado vía /auth/me, nunca del JWT decodificado
  // en el cliente: es la única fuente que el backend garantiza actualizada.
  const isAuditor = computed(() => user.value?.rol === RolUsuario.AUDITOR);

  async function login(email: string, password: string): Promise<void> {
    error.value = null;
    const result = await authApi.login(email, password);
    token.value = result.access_token;
    setStoredToken(result.access_token);
    await hydrate();
  }

  /** Carga /auth/me si hay token guardado; se llama al arrancar la app. */
  async function hydrate(): Promise<void> {
    if (!token.value) return;
    isHydrating.value = true;
    try {
      user.value = await authApi.me();
    } catch (err) {
      error.value = extractErrorMessage(err);
      logout();
    } finally {
      isHydrating.value = false;
    }
  }

  function logout(): void {
    token.value = null;
    user.value = null;
    setStoredToken(null);
  }

  registerUnauthorizedHandler(logout);

  return { token, user, isHydrating, error, isAuthenticated, isAuditor, login, hydrate, logout };
});
