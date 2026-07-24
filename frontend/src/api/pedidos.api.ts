import { http } from "./http";
import type { EstadoPedido } from "@/types/enums";
import type { PedidoCreate, PedidoRead, PedidoUpdate } from "@/types/models";

export const pedidosApi = {
  async list(estado?: EstadoPedido): Promise<PedidoRead[]> {
    const { data } = await http.get<PedidoRead[]>("/pedidos", {
      params: estado ? { estado } : undefined,
    });
    return data;
  },

  async get(id: string): Promise<PedidoRead> {
    const { data } = await http.get<PedidoRead>(`/pedidos/${id}`);
    return data;
  },

  async create(payload: PedidoCreate): Promise<PedidoRead> {
    const { data } = await http.post<PedidoRead>("/pedidos", payload);
    return data;
  },

  async update(id: string, payload: PedidoUpdate): Promise<PedidoRead> {
    const { data } = await http.patch<PedidoRead>(`/pedidos/${id}`, payload);
    return data;
  },
};
