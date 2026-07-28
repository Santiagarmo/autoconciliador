<script setup lang="ts">
import { ref } from "vue";

import BaseButton from "@/components/ui/BaseButton.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import { BANCOS_INGESTA_DISPONIBLES } from "@/types/enums";

const emit = defineEmits<{ submit: [payload: { banco: string; archivo: File }] }>();
defineProps<{ isSubmitting?: boolean }>();

const banco = ref("");
const archivo = ref<File | null>(null);
const bancoOptions = BANCOS_INGESTA_DISPONIBLES.map((b) => ({ value: b, label: b }));

function handleFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  archivo.value = input.files?.[0] ?? null;
}

function handleSubmit(): void {
  if (!archivo.value || !banco.value) return;
  emit("submit", { banco: banco.value, archivo: archivo.value });
}
</script>

<template>
  <form class="flex flex-col gap-4" @submit.prevent="handleSubmit">
    <BaseSelect
      v-model="banco"
      label="Banco del extracto"
      placeholder="Selecciona un banco"
      :options="bancoOptions"
      required
    />
    <div class="flex flex-col gap-1.5">
      <label class="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-fg-faint">
        Archivo PDF <span class="text-signal-neg">*</span>
      </label>
      <input
        type="file"
        accept="application/pdf"
        required
        class="border-b border-line pb-2 text-sm text-fg-muted file:mr-3 file:rounded-sm file:border-0 file:bg-steel-tint file:px-3 file:py-2 file:font-mono file:text-xs file:font-medium file:uppercase file:tracking-wide file:text-steel file:transition-colors hover:file:bg-steel/20"
        @change="handleFileChange"
      />
      <p class="text-xs text-fg-faint">
        El extracto se procesa en segundo plano; la conciliación corre automáticamente al terminar.
      </p>
    </div>
    <BaseButton type="submit" class="self-end" :loading="isSubmitting" :disabled="!archivo || !banco">
      Subir extracto
    </BaseButton>
  </form>
</template>
