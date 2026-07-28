<script setup lang="ts">
import { ref, nextTick } from "vue";

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

const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const id = `input-${Math.random().toString(36).slice(2, 9)}`;
const isFocused = ref(false);
const caretLeft = ref(0);
const inputEl = ref<HTMLInputElement | null>(null);
const mirrorEl = ref<HTMLSpanElement | null>(null);

async function updateCaretPosition() {
  await nextTick();
  if (!inputEl.value || !mirrorEl.value) return;
  const el = inputEl.value;
  const caretIndex = el.selectionStart ?? el.value.length;
  const visibleText = el.value.slice(0, caretIndex);
  mirrorEl.value.textContent = el.type === "password" ? "•".repeat(visibleText.length) : visibleText;
  caretLeft.value = mirrorEl.value.offsetWidth;
}

function handleInput(event: Event) {
  emit("update:modelValue", (event.target as HTMLInputElement).value);
  updateCaretPosition();
}

function handleFocus() {
  isFocused.value = true;
  updateCaretPosition();
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" :for="id" class="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-fg-faint">
      {{ label }}
      <span v-if="required" class="text-signal-neg">*</span>
    </label>
    <div class="relative flex items-center">
      <input
        :id="id"
        ref="inputEl"
        :type="type"
        :placeholder="placeholder"
        :required="required"
        :value="modelValue"
        class="w-full rounded-sm border-0 border-b-2 border-line bg-surface-sunk px-2.5 py-2 text-sm text-fg caret-transparent placeholder:text-fg-faint transition-[border-color,background-color] duration-200 focus:border-steel focus:outline-none"
        :class="{ 'border-signal-neg focus:border-signal-neg': error }"
        @input="handleInput"
        @focus="handleFocus"
        @blur="isFocused = false"
        @click="updateCaretPosition"
        @keyup="updateCaretPosition"
      />
      <span
        ref="mirrorEl"
        aria-hidden="true"
        class="pointer-events-none invisible absolute left-0 top-0 whitespace-pre text-sm"
      ></span>
      <span
        v-if="isFocused"
        aria-hidden="true"
        class="pointer-events-none absolute h-4 w-[1.5px] origin-center animate-cursor-expand bg-steel"
        :style="{ left: `calc(0.625rem + ${caretLeft}px)` }"
      />
    </div>
    <p v-if="error" class="text-xs text-signal-neg">{{ error }}</p>
    <p v-else-if="hint" class="text-xs text-fg-faint">{{ hint }}</p>
  </div>
</template>
