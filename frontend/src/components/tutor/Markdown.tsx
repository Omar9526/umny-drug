"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { cn } from "@/lib/utils";

/** Tutor text: Markdown + KaTeX. Links are rendered as plain text — no outbound links for children. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("prose-ud", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false, output: "html" }]]}
        components={{
          a: ({ children: inner }) => <span>{inner}</span>,
          img: () => null,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
