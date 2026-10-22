"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, authorizedFetch } from "@/lib/api/client";
import type {
  AIMessage,
  CheckAnswerResponse,
  QuickCommand,
  SessionDetail,
  SessionMode,
  SessionState,
} from "@/lib/api/types";

export interface CreateSessionInput {
  mode: Exclude<SessionMode, "homework">;
  subject_slug?: string | null;
  topic_id?: number | null;
  question?: string;
}

export const tutorApi = {
  create: (body: CreateSessionInput) => api<SessionDetail>("/api/v1/tutor/sessions/", { method: "POST", body }),
  get: (id: string) => api<SessionDetail>(`/api/v1/tutor/sessions/${id}/`),
  checkAnswer: (id: string, answer_text: string) =>
    api<CheckAnswerResponse>(`/api/v1/tutor/sessions/${id}/check-answer/`, { method: "POST", body: { answer_text } }),
  complete: (id: string) => api<SessionState>(`/api/v1/tutor/sessions/${id}/complete/`, { method: "POST" }),
  flag: (id: string, messageId: string, reason = "") =>
    api<AIMessage>(`/api/v1/tutor/sessions/${id}/messages/${messageId}/flag/`, { method: "POST", body: { reason } }),
};

export function useSession(id: string | null) {
  return useQuery({ queryKey: ["session", id], queryFn: () => tutorApi.get(id as string), enabled: Boolean(id) });
}

export function useCreateSession() {
  return useMutation({ mutationFn: tutorApi.create });
}

export function useInvalidateSessionLists() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["history"] });
  };
}

export interface StreamError {
  code: string;
  message: string;
  retryable?: boolean;
}

export interface TurnEvents {
  onDelta: (text: string) => void;
  /** A safety fallback replaced the draft: discard the text shown so far. */
  onReset?: () => void;
  onFinal: (data: { message: AIMessage; session: SessionState }) => void;
  onError: (error: StreamError) => void;
}

/** Parse one SSE block ("event: …\ndata: …"). Exported for unit tests. */
export function parseSseBlock(block: string): { event: string; data: unknown } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

/**
 * Streams one tutor turn over Server-Sent Events (POST + ReadableStream; EventSource cannot
 * send a bearer token). Resolves when the stream ends; every outcome is reported through the
 * handlers, including a stream that ended without a terminal event.
 */
export async function streamTurn(
  sessionId: string,
  body: { command: QuickCommand; content?: string },
  handlers: TurnEvents,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await authorizedFetch(`/api/v1/tutor/sessions/${sessionId}/messages/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ command: body.command, content: body.content ?? "" }),
      signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
    if (error instanceof ApiError) {
      handlers.onError({ code: error.code, message: error.message, retryable: error.status === 0 || error.status >= 500 });
      return;
    }
    handlers.onError({ code: "network", message: "Нет соединения с сервером.", retryable: true });
    return;
  }
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => null);
    const err = ApiError.fromResponse(response.status, payload);
    handlers.onError({ code: err.code, message: err.message, retryable: response.status === 429 || response.status >= 500 });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal = false;
  const dispatch = (block: string) => {
    const parsed = parseSseBlock(block);
    if (!parsed) return;
    if (parsed.event === "delta") handlers.onDelta((parsed.data as { text: string }).text ?? "");
    else if (parsed.event === "reset") handlers.onReset?.();
    else if (parsed.event === "final") {
      terminal = true;
      handlers.onFinal(parsed.data as { message: AIMessage; session: SessionState });
    } else if (parsed.event === "error") {
      terminal = true;
      handlers.onError(parsed.data as StreamError);
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx = buffer.indexOf("\n\n");
      while (idx >= 0) {
        dispatch(buffer.slice(0, idx));
        buffer = buffer.slice(idx + 2);
        idx = buffer.indexOf("\n\n");
      }
    }
    if (buffer.trim()) dispatch(buffer);
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
    handlers.onError({ code: "stream", message: "Связь прервалась. Попробуй ещё раз.", retryable: true });
    return;
  }
  if (!terminal && !signal?.aborted) {
    handlers.onError({ code: "incomplete", message: "Ответ оборвался. Попробуй ещё раз.", retryable: true });
  }
}
