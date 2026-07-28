import { http } from "./http";
import type { MovimientoBancarioRead, VerificacionExtractoRead } from "@/types/models";

export const movimientosApi = {
  async list(): Promise<MovimientoBancarioRead[]> {
    const { data } = await http.get<MovimientoBancarioRead[]>("/movimientos");
    return data;
  },

  /** Últimas ingestas y su veredicto de StatementVerifier (+ LLM cuando aplique). */
  async listVerificaciones(limit = 20): Promise<VerificacionExtractoRead[]> {
    const { data } = await http.get<VerificacionExtractoRead[]>("/movimientos/verificaciones", {
      params: { limit },
    });
    return data;
  },

  /** El backend responde 202 de inmediato; parseo + conciliación corren en background. */
  async ingestar(banco: string, archivo: File): Promise<string> {
    const form = new FormData();
    form.set("banco", banco);
    form.set("archivo", archivo);
    const { data } = await http.post<{ detail: string }>("/movimientos/ingesta", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data.detail;
  },
};
