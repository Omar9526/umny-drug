"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  AvatarKey,
  ChildProgress,
  ConsentRecord,
  Family,
  FamilySettings,
  Language,
  Paginated,
  ParentNotification,
  ParentOverview,
  ParentSessionDetail,
  SessionStatus,
  SessionSummary,
  StudentProfile,
} from "@/lib/api/types";

export interface CreateChildInput {
  nickname: string;
  grade_id: number;
  instruction_language: Language;
  explanation_language: Language;
  avatar: string;
  pin: string;
  consent_confirmed: boolean;
}

export interface ChildUpdateInput {
  nickname?: string;
  avatar?: AvatarKey;
  grade_id?: number;
  instruction_language?: Language;
  explanation_language?: Language;
  share_conversations_with_parent?: boolean;
  allow_photo_upload?: boolean;
  allow_free_questions?: boolean;
}

export interface ChildSessionsFilter {
  status?: SessionStatus | "needs_review" | "";
  subject?: string;
}

const BASE = "/api/v1/parents";

export const parentApi = {
  children: () => api<StudentProfile[]>(`${BASE}/children/`),
  child: (id: string) => api<StudentProfile>(`${BASE}/children/${id}/`),
  createChild: (input: CreateChildInput) => api<StudentProfile>(`${BASE}/children/`, { method: "POST", body: input }),
  updateChild: (id: string, input: ChildUpdateInput) =>
    api<StudentProfile>(`${BASE}/children/${id}/`, { method: "PATCH", body: input }),
  deactivateChild: (id: string) => api<void>(`${BASE}/children/${id}/`, { method: "DELETE" }),
  eraseChild: (id: string) =>
    api<{ erased: Record<string, number> }>(`${BASE}/children/${id}/erase/`, { method: "POST" }),
  setPin: (childId: string, pin: string) =>
    api<void>(`${BASE}/children/${childId}/pin/`, { method: "POST", body: { pin } }),
  progress: (id: string) => api<ChildProgress>(`${BASE}/children/${id}/progress/`),
  sessions: (id: string, filter: ChildSessionsFilter, page: number) => {
    const params = new URLSearchParams({ page: String(page) });
    if (filter.status === "needs_review") params.set("outcome", "needs_review");
    else if (filter.status) params.set("status", filter.status);
    if (filter.subject) params.set("subject", filter.subject);
    return api<Paginated<SessionSummary>>(`${BASE}/children/${id}/sessions/?${params.toString()}`);
  },
  session: (id: string, sessionId: string) =>
    api<ParentSessionDetail>(`${BASE}/children/${id}/sessions/${sessionId}/`),
  overview: () => api<ParentOverview>(`${BASE}/overview/`),
  family: () => api<Family>(`${BASE}/family/`),
  rotateCode: () => api<Family>(`${BASE}/family/rotate-code/`, { method: "POST" }),
  deleteFamily: (password: string) =>
    api<{ children_erased: number }>(`${BASE}/family/delete/`, {
      method: "POST",
      body: { password, confirm: true },
    }),
  settings: () => api<FamilySettings>(`${BASE}/settings/`),
  updateSettings: (input: Partial<FamilySettings>) =>
    api<FamilySettings>(`${BASE}/settings/`, { method: "PATCH", body: input }),
  notifications: (unread: boolean, page: number) => {
    const params = new URLSearchParams({ page: String(page) });
    if (unread) params.set("unread", "1");
    return api<Paginated<ParentNotification>>(`${BASE}/notifications/?${params.toString()}`);
  },
  markRead: (id?: string) =>
    api<{ updated: number }>(id ? `${BASE}/notifications/${id}/read/` : `${BASE}/notifications/read-all/`, {
      method: "POST",
    }),
  consents: () => api<ConsentRecord[]>(`${BASE}/consents/`),
  revokeConsent: (id: string) => api<ConsentRecord>(`${BASE}/consents/${id}/revoke/`, { method: "POST" }),
};

export function useChildren() {
  return useQuery({ queryKey: ["parent", "children"], queryFn: parentApi.children });
}

export function useChild(id: string) {
  return useQuery({ queryKey: ["parent", "child", id], queryFn: () => parentApi.child(id) });
}

export function useOverview() {
  return useQuery({ queryKey: ["parent", "overview"], queryFn: parentApi.overview, staleTime: 15_000 });
}

export function useChildProgress(id: string) {
  return useQuery({ queryKey: ["parent", "progress", id], queryFn: () => parentApi.progress(id) });
}

export function useChildSessions(id: string, filter: ChildSessionsFilter) {
  return useInfiniteQuery({
    queryKey: ["parent", "sessions", id, filter.status ?? "", filter.subject ?? ""],
    initialPageParam: 1,
    queryFn: ({ pageParam }) => parentApi.sessions(id, filter, pageParam),
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
  });
}

export function useChildSession(id: string, sessionId: string) {
  return useQuery({
    queryKey: ["parent", "session", id, sessionId],
    queryFn: () => parentApi.session(id, sessionId),
  });
}

export function useFamily() {
  return useQuery({ queryKey: ["parent", "family"], queryFn: parentApi.family });
}

export function useFamilySettings() {
  return useQuery({ queryKey: ["parent", "settings"], queryFn: parentApi.settings });
}

export function useConsents() {
  return useQuery({ queryKey: ["parent", "consents"], queryFn: parentApi.consents });
}

export function useNotifications(unread = false) {
  return useInfiniteQuery({
    queryKey: ["parent", "notifications", unread ? "unread" : "all"],
    initialPageParam: 1,
    queryFn: ({ pageParam }) => parentApi.notifications(unread, pageParam),
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
  });
}

function useInvalidateParent() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["parent"] });
}

export function useCreateChild() {
  const invalidate = useInvalidateParent();
  return useMutation({ mutationFn: parentApi.createChild, onSuccess: invalidate });
}

export function useUpdateChild(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ChildUpdateInput) => parentApi.updateChild(id, input),
    onSuccess: (child) => {
      queryClient.setQueryData(["parent", "child", id], child);
      queryClient.invalidateQueries({ queryKey: ["parent", "overview"] });
      queryClient.invalidateQueries({ queryKey: ["parent", "children"] });
      queryClient.invalidateQueries({ queryKey: ["parent", "progress", id] });
      queryClient.invalidateQueries({ queryKey: ["parent", "session", id] });
    },
  });
}

export function useDeactivateChild(id: string) {
  const invalidate = useInvalidateParent();
  return useMutation({ mutationFn: () => parentApi.deactivateChild(id), onSuccess: invalidate });
}

export function useEraseChild(id: string) {
  const invalidate = useInvalidateParent();
  return useMutation({ mutationFn: () => parentApi.eraseChild(id), onSuccess: invalidate });
}

export function useSetPin(childId: string) {
  return useMutation({ mutationFn: (pin: string) => parentApi.setPin(childId, pin) });
}

export function useRotateCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: parentApi.rotateCode,
    onSuccess: (family) => {
      queryClient.setQueryData(["parent", "family"], family);
      queryClient.invalidateQueries({ queryKey: ["parent", "overview"] });
    },
  });
}

export function useUpdateFamilySettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: parentApi.updateSettings,
    onSuccess: (settings) => queryClient.setQueryData(["parent", "settings"], settings),
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id?: string) => parentApi.markRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["parent", "notifications"] });
      queryClient.invalidateQueries({ queryKey: ["parent", "overview"] });
    },
  });
}

export function useRevokeConsent() {
  const invalidate = useInvalidateParent();
  return useMutation({ mutationFn: parentApi.revokeConsent, onSuccess: invalidate });
}

export function useDeleteFamily() {
  return useMutation({ mutationFn: parentApi.deleteFamily });
}
