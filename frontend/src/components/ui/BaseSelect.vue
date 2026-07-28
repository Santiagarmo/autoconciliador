<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: string;
    label?: string;
    options: { value: string; label: string }[];
    placeholder?: string;
    required?: boolean;
  }>(),
  { required: false },
);

defineEmits<{ "update:modelValue": [value: string] }>();

const id = `select-${Math.random().toString(36).slice(2, 9)}`;
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" :for="id" class="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-fg-faint">
      {{ label }}
      <span v-if="required" class="text-signal-neg">*</span>
    </label>
    <select
      :id="id"
      :required="required"
      :value="modelValue"
      class="rounded-sm border-0 border-b-2 border-line bg-surface-sunk px-2.5 py-2 text-sm text-fg transition-[border-color,background-color] duration-200 focus:border-steel focus:outline-none"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
  </div>
</template>
