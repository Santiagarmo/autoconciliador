<script setup lang="ts">
import { onMounted } from "vue";
import { useRoute } from "vue-router";

import AppShell from "@/components/layout/AppShell.vue";
import ToastContainer from "@/components/ui/ToastContainer.vue";
import { useAuthStore } from "@/stores/auth.store";

const auth = useAuthStore();
const route = useRoute();

onMounted(() => {
  if (auth.token) auth.hydrate();
});
</script>

<template>
  <ToastContainer />
  <AppShell v-if="!route.meta.public">
    <router-view />
  </AppShell>
  <router-view v-else />
</template>
