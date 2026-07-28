<script setup lang="ts">
/**
 * Traduce cualquiera de los 4 enums de estado del dominio a un `BaseBadge`,
 * apoyándose en los mapas de `types/enums.ts`. Soportar un estado nuevo es
 * agregar una entrada al mapa correspondiente, no tocar este componente.
 */
import { computed } from "vue";

import BaseBadge from "@/components/ui/BaseBadge.vue";
import {
  ESTADO_MOVIMIENTO_META,
  ESTADO_PAGO_META,
  ESTADO_PEDIDO_META,
  RESULTADO_VERIFICACION_META,
  TIPO_CONCILIACION_META,
  type BadgeVariant,
  type EstadoMovimiento,
  type EstadoPago,
  type EstadoPedido,
  type ResultadoVerificacion,
  type TipoConciliacion,
} from "@/types/enums";

const props = defineProps<{
  kind: "pedido" | "pago" | "movimiento" | "conciliacion" | "verificacion";
  estado: EstadoPedido | EstadoPago | EstadoMovimiento | TipoConciliacion | ResultadoVerificacion;
}>();

interface StatusMeta {
  label: string;
  variant: BadgeVariant;
}

const META_BY_KIND: Record<typeof props.kind, Record<string, StatusMeta>> = {
  pedido: ESTADO_PEDIDO_META,
  pago: ESTADO_PAGO_META,
  movimiento: ESTADO_MOVIMIENTO_META,
  conciliacion: TIPO_CONCILIACION_META,
  verificacion: RESULTADO_VERIFICACION_META,
};

const meta = computed<StatusMeta>(() => {
  const map = META_BY_KIND[props.kind];
  return map[props.estado] ?? { label: props.estado, variant: "neutral" };
});
</script>

<template>
  <BaseBadge :label="meta.label" :variant="meta.variant" />
</template>
