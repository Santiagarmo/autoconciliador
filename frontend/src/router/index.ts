import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth.store";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/LoginView.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      name: "dashboard",
      component: () => import("@/views/DashboardView.vue"),
    },
    {
      path: "/pedidos/:id",
      name: "pedido-detail",
      component: () => import("@/views/PedidoDetailView.vue"),
      props: true,
    },
    {
      path: "/pagos",
      name: "pagos",
      component: () => import("@/views/PagosView.vue"),
    },
    {
      path: "/movimientos",
      name: "movimientos",
      component: () => import("@/views/MovimientosView.vue"),
    },
    {
      path: "/conciliaciones",
      name: "conciliaciones",
      component: () => import("@/views/ConciliacionesView.vue"),
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/",
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();

  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isAuthenticated) {
    return { name: "dashboard" };
  }
  return true;
});

export default router;
