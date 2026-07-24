<script setup lang="ts">
import { reactive } from "vue";

import BaseButton from "@/components/ui/BaseButton.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import type { PedidoCreate } from "@/types/models";

const emit = defineEmits<{ submit: [payload: PedidoCreate] }>();
defineProps<{ isSubmitting?: boolean }>();

const form = reactive<PedidoCreate>({
  codigo_pedido: "",
  cliente_whatsapp: "",
  monto_total: "",
});

function handleSubmit(): void {
  emit("submit", { ...form });
}
</script>

<template>
  <form class="flex flex-col gap-4" @submit.prevent="handleSubmit">
    <BaseInput
      v-model="form.codigo_pedido"
      label="Código de pedido"
      placeholder="PED-1042"
      required
    />
    <BaseInput
      v-model="form.cliente_whatsapp"
      label="WhatsApp del cliente"
      placeholder="+57 300 123 4567"
      required
    />
    <BaseInput
      v-model="form.monto_total"
      label="Monto total"
      type="number"
      placeholder="150000"
      hint="Pesos colombianos, sin decimales de más."
      required
    />
    <BaseButton type="submit" class="self-end" :loading="isSubmitting">
      Crear pedido
    </BaseButton>
  </form>
</template>
