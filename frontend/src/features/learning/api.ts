"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { KnowledgeMap, QuizAnswerResponse, QuizAttempt } from "@/lib/api/types";

export const learningApi = {
  map: (subject: string, studentId?: string) => {
    const params = new URLSearchParams({ subject });
    if (studentId) params.set("student", studentId);
    return api<KnowledgeMap>(`/api/v1/learning/map/?${params.toString()}`);
  },
  startQuiz: (topicId: number) =>
    api<QuizAttempt>("/api/v1/quizzes/start/", { method: "POST", body: { topic_id: topicId } }),
  attempt: (id: string) => api<QuizAttempt>(`/api/v1/quizzes/attempts/${id}/`),
  answer: (id: string, questionId: number, answer: string | string[]) =>
    api<QuizAnswerResponse>(`/api/v1/quizzes/attempts/${id}/answer/`, {
      method: "POST",
      body: { question_id: questionId, answer },
    }),
  finish: (id: string) => api<QuizAttempt>(`/api/v1/quizzes/attempts/${id}/finish/`, { method: "POST" }),
};

export function useKnowledgeMap(subject: string | null, studentId?: string) {
  return useQuery({
    queryKey: ["map", subject, studentId ?? "me"],
    queryFn: () => learningApi.map(subject as string, studentId),
    enabled: Boolean(subject),
  });
}

export function useQuizAttempt(id: string | null) {
  return useQuery({
    queryKey: ["quiz", id],
    queryFn: () => learningApi.attempt(id as string),
    enabled: Boolean(id),
  });
}

/** Invalidate everything that shows topic status after a quiz changes it. */
export function useInvalidateProgress() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["map"] });
    queryClient.invalidateQueries({ queryKey: ["subject"] });
    queryClient.invalidateQueries({ queryKey: ["subjects"] });
    queryClient.invalidateQueries({ queryKey: ["topic"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
}

export function useStartQuiz() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: learningApi.startQuiz,
    onSuccess: (attempt) => queryClient.setQueryData(["quiz", attempt.id], attempt),
  });
}

export function useAnswerQuestion(attemptId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ questionId, answer }: { questionId: number; answer: string | string[] }) =>
      learningApi.answer(attemptId, questionId, answer),
    onSuccess: (result, variables) => {
      queryClient.setQueryData<QuizAttempt>(["quiz", attemptId], (prev) => {
        if (!prev) return prev;
        const key = String(variables.questionId);
        const results = {
          ...prev.results,
          [key]: {
            correct: result.correct,
            explanation: result.explanation,
            correct_answer: result.correct_answer,
            checked_at: new Date().toISOString(),
          },
        };
        return {
          ...prev,
          answers: { ...prev.answers, [key]: variables.answer },
          results,
          correct_count: Object.values(results).filter((r) => r.correct).length,
        };
      });
    },
  });
}

export function useFinishQuiz(attemptId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateProgress();
  return useMutation({
    mutationFn: () => learningApi.finish(attemptId),
    onSuccess: (attempt) => {
      queryClient.setQueryData(["quiz", attemptId], attempt);
      invalidate();
    },
  });
}
