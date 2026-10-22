"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, authorizedFetch } from "@/lib/api/client";
import type { AssignmentDetail, Language, SessionSummary, Upload } from "@/lib/api/types";

export interface UploadInput {
  source: "camera" | "gallery" | "text";
  files?: File[];
  typedText?: string;
  languageHint?: Language;
}

export const assignmentsApi = {
  upload: ({ source, files = [], typedText = "", languageHint }: UploadInput) => {
    const form = new FormData();
    form.set("source", source);
    if (typedText) form.set("typed_text", typedText);
    if (languageHint) form.set("language_hint", languageHint);
    for (const file of files) form.append("images", file, file.name || "photo.jpg");
    return api<Upload>("/api/v1/assignments/upload/", { method: "POST", formData: form });
  },
  getUpload: (id: string) => api<Upload>(`/api/v1/assignments/uploads/${id}/`),
  retryUpload: (id: string) => api<Upload>(`/api/v1/assignments/uploads/${id}/retry/`, { method: "POST" }),
  getAssignment: (id: string) => api<AssignmentDetail>(`/api/v1/assignments/${id}/`),
  confirm: (id: string, body: { confirmed_text: string; subject_slug?: string | null; topic_id?: number | null }) =>
    api<{ assignment: AssignmentDetail; session: SessionSummary }>(`/api/v1/assignments/${id}/confirm/`, {
      method: "POST",
      body,
    }),
};

const ACTIVE: Upload["status"][] = ["pending", "processing"];

export function useUpload(id: string | null) {
  return useQuery({
    queryKey: ["upload", id],
    queryFn: () => assignmentsApi.getUpload(id as string),
    enabled: Boolean(id),
    refetchInterval: (query) => (query.state.data && ACTIVE.includes(query.state.data.status) ? 1500 : false),
  });
}

export function useAssignment(id: string | null) {
  return useQuery({
    queryKey: ["assignment", id],
    queryFn: () => assignmentsApi.getAssignment(id as string),
    enabled: Boolean(id),
  });
}

export function useUploadMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: assignmentsApi.upload,
    onSuccess: (upload) => queryClient.setQueryData(["upload", upload.id], upload),
  });
}

export function useConfirmAssignment(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof assignmentsApi.confirm>[1]) => assignmentsApi.confirm(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assignment", id] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["history"] });
    },
  });
}

/** Private images need the bearer token, so they are fetched as blobs and shown via object URLs. */
export function useImageObjectUrl(imageId: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!imageId) return;
    let revoked = false;
    let objectUrl: string | null = null;
    authorizedFetch(`/api/v1/assignments/images/${imageId}/`)
      .then(async (res) => {
        if (!res.ok) return;
        const blob = await res.blob();
        if (revoked) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => undefined);
    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [imageId]);
  return url;
}
