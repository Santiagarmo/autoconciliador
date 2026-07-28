<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import BaseButton from "@/components/ui/BaseButton.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import { extractErrorMessage } from "@/api/http";
import { useAuthStore } from "@/stores/auth.store";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const email = ref("");
const password = ref("");
const isSubmitting = ref(false);
const errorMessage = ref<string | null>(null);

async function handleSubmit(): Promise<void> {
  isSubmitting.value = true;
  errorMessage.value = null;
  try {
    await auth.login(email.value, password.value);
    const redirect = (route.query.redirect as string) || "/";
    router.push(redirect);
  } catch (err) {
    errorMessage.value = extractErrorMessage(err, "No se pudo iniciar sesión.");
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="flex min-h-screen bg-surface-raised">
    <div class="relative hidden w-1/2 overflow-hidden border-r border-line bg-surface text-fg md:block">
      <div
        class="pointer-events-none absolute inset-0 animate-grid-drift opacity-[0.07]"
        style="background-image: repeating-linear-gradient(to bottom, transparent, transparent 47px, currentColor 47px, currentColor 48px)"
      />
      <div
        class="pointer-events-none absolute inset-x-0 top-0 h-24 animate-scanline bg-gradient-to-b from-transparent via-steel/25 to-transparent"
      />
      <div class="stagger relative flex h-full flex-col justify-between px-12 py-14" style="--stagger-step: 70ms">
        <span class="font-mono text-xs uppercase tracking-[0.2em] text-fg/50">
          AC / Terminal de conciliación
        </span>
        <div class="stagger flex flex-col gap-4" style="--stagger-step: 70ms">
          <h1 class="animate-rise-lg font-display text-display">
            Auto<br />Conciliador
          </h1>
          <p class="max-w-xs font-mono text-sm text-fg/60">
            Conciliación bancaria B2B para ventas por WhatsApp.
          </p>
        </div>
        <p class="font-mono text-[11px] uppercase tracking-[0.14em] text-fg/40">
          Pedidos · Pagos · Movimientos · Conciliaciones
        </p>
      </div>
    </div>

    <div class="flex flex-1 items-center justify-center px-6 py-14">
      <div class="stagger w-full max-w-sm">
        <div class="mb-8 md:hidden">
          <h1 class="font-display text-title text-fg">AutoConciliador</h1>
          <p class="mt-1 font-mono text-xs text-fg-faint">Conciliación bancaria B2B por WhatsApp</p>
        </div>

        <p class="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-fg-faint">Acceso operador</p>

        <form class="stagger flex flex-col gap-5" style="--stagger-step: 70ms" @submit.prevent="handleSubmit">
          <BaseInput v-model="email" type="email" label="Email" placeholder="operador@empresa.com" required />
          <BaseInput v-model="password" type="password" label="Contraseña" required />

          <p v-if="errorMessage" class="rounded-sm border-l-2 border-signal-neg bg-signal-neg/10 px-3 py-2 text-sm text-signal-neg">
            {{ errorMessage }}
          </p>

          <BaseButton type="submit" class="mt-2 w-full justify-center" :loading="isSubmitting">
            Iniciar sesión
          </BaseButton>
        </form>
      </div>
    </div>
  </div>
</template>
