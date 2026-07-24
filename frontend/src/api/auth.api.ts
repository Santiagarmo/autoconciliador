import { http } from "./http";
import type { Token, UserCreate, UserRead } from "@/types/models";

export const authApi = {
  /** Login OAuth2 password flow: el backend espera form-urlencoded, no JSON. */
  async login(email: string, password: string): Promise<Token> {
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);
    const { data } = await http.post<Token>("/auth/login", body, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    return data;
  },

  async me(): Promise<UserRead> {
    const { data } = await http.get<UserRead>("/auth/me");
    return data;
  },

  /** Restringido a AUDITOR en el backend; el 403 se propaga si no aplica. */
  async createUser(payload: UserCreate): Promise<UserRead> {
    const { data } = await http.post<UserRead>("/auth/users", payload);
    return data;
  },
};
