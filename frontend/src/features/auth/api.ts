import { api } from "@/lib/api/client";
import type { AppMeta, AuthResponse, ChildLookupResponse, Language } from "@/lib/api/types";

export interface RegisterParentInput {
  display_name: string;
  email: string;
  password: string;
  preferred_language: Language;
  consents: { terms: boolean; privacy: boolean; marketing: boolean };
}

export const authApi = {
  registerParent: (input: RegisterParentInput) =>
    api<AuthResponse>("/api/v1/auth/parent/register/", { method: "POST", body: input, auth: false }),
  login: (email: string, password: string) =>
    api<AuthResponse>("/api/v1/auth/login/", { method: "POST", body: { email, password }, auth: false }),
  childLookup: (family_code: string) =>
    api<ChildLookupResponse>("/api/v1/auth/child/lookup/", { method: "POST", body: { family_code }, auth: false }),
  childLogin: (family_code: string, student_id: string, pin: string) =>
    api<AuthResponse>("/api/v1/auth/child/login/", {
      method: "POST",
      body: { family_code, student_id, pin },
      auth: false,
    }),
  meta: () => api<AppMeta>("/api/v1/meta/", { auth: false }),
};
