<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: string;
    label?: string;
    type?: string;
    placeholder?: string;
    required?: boolean;
    error?: string | null;
    hint?: string;
  }>(),
  { type: "text", required: false, error: null },
);

defineEmits<{ "update:modelValue": [value: string] }>();

const id = `input-${Math.random().toString(36).slice(2, 9)}`;
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" :for="id" class="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-ink-faint">
      {{ label }}
      <span v-if="required" class="text-oxide">*</span>
    </label>
    <input
      :id="id"
      :type="type"
      :placeholder="placeholder"
      :required="required"
      :value="modelValue"
      class="border-0 border-b border-rule bg-transparent px-0.5 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-b-2 focus:border-ochre focus:outline-none"
      :class="{ 'border-oxide focus:border-oxide': error }"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="error" class="text-xs text-oxide">{{ error }}</p>
    <p v-else-if="hint" class="text-xs text-ink-faint">{{ hint }}</p>
  </div>
</template>
