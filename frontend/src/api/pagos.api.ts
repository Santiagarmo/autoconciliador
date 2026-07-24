import { http } from "./http";
import type { PagoDeclaradoCreate, PagoDeclaradoRead } from "@/types/models";

export const pagosApi = {
  async list(): Promise<PagoDeclaradoRead[]> {
    const { data } = await http.get<PagoDeclaradoRead[]>("/pagos");
    return data;
  },

  async create(payload: PagoDeclaradoCreate): Promise<PagoDeclaradoRead> {
    const { data } = await http.post<PagoDeclaradoRead>("/pagos", payload);
    return data;
  },
};
