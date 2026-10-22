"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { Dashboard, Paginated, SessionStatus, SessionSummary, StudentProfile } from "@/lib/api/types";
import { useAuth } from "@/features/auth/AuthProvider";

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/api/v1/students/me/dashboard/") });
}

export interface StudentUpdateInput {
  avatar?: string;
  instruction_language?: "ru" | "ky";
  explanation_language?: "ru" | "ky";
  grade_id?: number;
  onboarding_completed?: boolean;
}

/** PATCH the student's own profile and keep the auth context + dashboard in sync. */
export function useUpdateStudent() {
  const { user, setUser } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StudentUpdateInput) =>
      api<StudentProfile>("/api/v1/students/me/", { method: "PATCH", body: input }),
    onSuccess: (profile) => {
      if (user) setUser({ ...user, preferred_language: profile.explanation_language, student: profile });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["subjects"] });
      queryClient.invalidateQueries({ queryKey: ["subject"] });
    },
  });
}

export function useHistory(status?: SessionStatus | "") {
  return useInfiniteQuery({
    queryKey: ["history", status ?? ""],
    initialPageParam: 1,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ page: String(pageParam) });
      if (status) params.set("status", status);
      return api<Paginated<SessionSummary>>(`/api/v1/learning/history/?${params.toString()}`);
    },
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
  });
}
