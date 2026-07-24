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
  <div class="flex min-h-screen bg-paper">
    <div class="relative hidden w-1/2 overflow-hidden bg-ink text-paper md:block">
      <div
        class="pointer-events-none absolute inset-0 opacity-[0.07]"
        style="background-image: repeating-linear-gradient(to bottom, transparent, transparent 47px, currentColor 47px, currentColor 48px)"
      />
      <div class="stagger relative flex h-full flex-col justify-between px-12 py-14">
        <span class="font-mono text-xs uppercase tracking-[0.2em] text-paper/60">
          AC / Libro mayor digital
        </span>
        <div class="flex flex-col gap-4">
          <h1 class="font-display text-6xl font-medium leading-[0.95]">
            Auto<br />Conciliador
          </h1>
          <p class="max-w-xs font-mono text-sm text-paper/60">
            Conciliación bancaria B2B para ventas por WhatsApp.
          </p>
        </div>
        <p class="font-mono text-[11px] uppercase tracking-[0.14em] text-paper/40">
          Pedidos · Pagos · Movimientos · Conciliaciones
        </p>
      </div>
    </div>

    <div class="flex flex-1 items-center justify-center px-6 py-14">
      <div class="stagger w-full max-w-sm">
        <div class="mb-8 md:hidden">
          <h1 class="font-display text-3xl text-ink">AutoConciliador</h1>
          <p class="mt-1 font-mono text-xs text-ink-faint">Conciliación bancaria B2B por WhatsApp</p>
        </div>

        <p class="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-faint">Acceso operador</p>

        <form class="flex flex-col gap-5" @submit.prevent="handleSubmit">
          <BaseInput v-model="email" type="email" label="Email" placeholder="operador@empresa.com" required />
          <BaseInput v-model="password" type="password" label="Contraseña" required />

          <p v-if="errorMessage" class="border-l-2 border-oxide bg-oxide/5 px-3 py-2 text-sm text-oxide">
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
