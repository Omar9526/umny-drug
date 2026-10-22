"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { Curriculum, Subject, SubjectDetail, TopicDetail } from "@/lib/api/types";

export const curriculumApi = {
  curricula: () => api<Curriculum[]>("/api/v1/curricula/", { auth: false }),
  subjects: (gradeId?: number) => api<Subject[]>(`/api/v1/subjects/${gradeId ? `?grade=${gradeId}` : ""}`),
  topic: (id: number) => api<TopicDetail>(`/api/v1/topics/${id}/`),
  subject: (slug: string, gradeId?: number) =>
    api<SubjectDetail>(`/api/v1/subjects/${encodeURIComponent(slug)}/${gradeId ? `?grade=${gradeId}` : ""}`),
};

export function useCurricula() {
  return useQuery({ queryKey: ["curricula"], queryFn: curriculumApi.curricula, staleTime: 60 * 60 * 1000 });
}

/** Student: own grade. Parent: pass the child's grade and `waitForGrade` so nothing is fetched before it is known. */
export function useSubjects(gradeId?: number, options: { waitForGrade?: boolean } = {}) {
  return useQuery({
    queryKey: ["subjects", gradeId ?? "me"],
    queryFn: () => curriculumApi.subjects(gradeId),
    enabled: options.waitForGrade ? gradeId !== undefined : true,
  });
}

export function useSubject(slug: string, gradeId?: number) {
  return useQuery({
    queryKey: ["subject", slug, gradeId ?? "me"],
    queryFn: () => curriculumApi.subject(slug, gradeId),
    enabled: Boolean(slug),
  });
}

export function useTopic(id: number | null) {
  return useQuery({ queryKey: ["topic", id], queryFn: () => curriculumApi.topic(id as number), enabled: Boolean(id) });
}
