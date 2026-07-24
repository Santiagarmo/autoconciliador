import { http } from "./http";
import type { ConciliacionRead, ReconSummaryRead } from "@/types/models";

export const conciliacionesApi = {
  async list(): Promise<ConciliacionRead[]> {
    const { data } = await http.get<ConciliacionRead[]>("/conciliaciones");
    return data;
  },

  /** Restringido a AUDITOR en el backend. */
  async run(): Promise<ReconSummaryRead> {
    const { data } = await http.post<ReconSummaryRead>("/conciliaciones/run");
    return data;
  },
};
