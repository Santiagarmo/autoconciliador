<script setup lang="ts">
import { useRouter } from "vue-router";

import BaseButton from "@/components/ui/BaseButton.vue";
import { ROL_USUARIO_META } from "@/types/enums";
import { useAuthStore } from "@/stores/auth.store";

const auth = useAuthStore();
const router = useRouter();

function handleLogout(): void {
  auth.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <header class="flex h-14 items-center justify-between border-b border-line bg-surface-raised px-4 sm:px-6">
    <span class="font-display text-base text-fg lg:hidden">AutoConciliador</span>
    <div class="ml-auto flex items-center gap-4">
      <div v-if="auth.user" class="text-right font-mono text-xs">
        <p class="text-fg">{{ auth.user.email }}</p>
        <p class="text-fg-faint uppercase tracking-wide">{{ ROL_USUARIO_META[auth.user.rol].label }}</p>
      </div>
      <BaseButton variant="ghost" @click="handleLogout">Salir</BaseButton>
    </div>
  </header>
</template>
