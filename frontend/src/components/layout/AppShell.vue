<script setup lang="ts">
import AppHeader from "./AppHeader.vue";
import AppSidebar from "./AppSidebar.vue";
</script>

<template>
  <div class="flex min-h-screen bg-paper">
    <AppSidebar />
    <div class="flex min-w-0 flex-1 flex-col">
      <AppHeader />
      <main class="flex-1 px-4 py-8 sm:px-6 lg:px-10">
        <div class="mx-auto max-w-[1400px]">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
