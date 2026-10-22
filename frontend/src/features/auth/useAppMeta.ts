"use client";

import { useQuery } from "@tanstack/react-query";
import { authApi } from "./api";

export function useAppMeta() {
  return useQuery({
    queryKey: ["meta"],
    queryFn: authApi.meta,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
