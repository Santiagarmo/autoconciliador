import { computed } from "vue";

import { useAuthStore } from "@/stores/auth.store";

/**
 * Centraliza las reglas de gating por rol para que las vistas no repitan
 * `user.rol === 'AUDITOR'` por todos lados. Si la regla de negocio cambia
 * (p.ej. un tercer rol con permisos parciales) solo se toca este archivo.
 */
export function useRole() {
  const auth = useAuthStore();

  const isAuditor = computed(() => auth.isAuditor);
  const canRunReconciliation = isAuditor;
  const canCreateUser = isAuditor;
  const canDespachar = isAuditor;

  return { isAuditor, canRunReconciliation, canCreateUser, canDespachar };
}
