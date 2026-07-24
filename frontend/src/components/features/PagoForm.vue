<script setup lang="ts">
import { computed, reactive } from "vue";

import BaseButton from "@/components/ui/BaseButton.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import { BANCOS_DECLARABLES } from "@/types/enums";
import type { PagoDeclaradoCreate, PedidoRead } from "@/types/models";

const props = defineProps<{ pedidos: PedidoRead[]; isSubmitting?: boolean }>();
const emit = defineEmits<{ submit: [payload: PagoDeclaradoCreate] }>();

const form = reactive({
  pedido_id: "",
  banco_destino: "",
  monto_declarado: "",
  numero_referencia: "",
  ultimos_4_digitos: "",
});

const pedidoOptions = computed(() =>
  props.pedidos.map((p) => ({ value: p.id, label: `${p.codigo_pedido} · ${p.cliente_whatsapp}` })),
);
const bancoOptions = BANCOS_DECLARABLES.map((b) => ({ value: b, label: b }));

function handleSubmit(): void {
  emit("submit", {
    pedido_id: form.pedido_id,
    banco_destino: form.banco_destino,
    monto_declarado: form.monto_declarado,
    numero_referencia: form.numero_referencia,
    ultimos_4_digitos: form.ultimos_4_digitos || null,
  });
}
</script>

<template>
  <form class="flex flex-col gap-4" @submit.prevent="handleSubmit">
    <BaseSelect
      v-model="form.pedido_id"
      label="Pedido"
      placeholder="Selecciona un pedido"
      :options="pedidoOptions"
      required
    />
    <BaseSelect
      v-model="form.banco_destino"
      label="Banco destino"
      placeholder="Selecciona un banco"
      :options="bancoOptions"
      required
    />
    <BaseInput
      v-model="form.monto_declarado"
      label="Monto declarado"
      type="number"
      placeholder="150000"
      required
    />
    <BaseInput
      v-model="form.numero_referencia"
      label="Número de referencia"
      placeholder="Referencia del comprobante"
      hint="Tal como aparece en la foto que envió el cliente por WhatsApp."
      required
    />
    <BaseInput
      v-model="form.ultimos_4_digitos"
      label="Últimos 4 dígitos (opcional)"
      placeholder="1234"
    />
    <BaseButton type="submit" class="self-end" :loading="isSubmitting">
      Registrar pago
    </BaseButton>
  </form>
</template>
