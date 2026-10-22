import { describe, expect, it } from "vitest";
import { parseSseBlock } from "./api";

describe("SSE block parsing", () => {
  it("reads event name and JSON data", () => {
    expect(parseSseBlock('event: delta\ndata: {"text":"Прив"}')).toEqual({ event: "delta", data: { text: "Прив" } });
  });

  it("defaults the event to message and joins multi-line data", () => {
    expect(parseSseBlock('data: {"a":\ndata: 1}')).toEqual({ event: "message", data: { a: 1 } });
  });

  it("ignores blocks without data or with broken JSON", () => {
    expect(parseSseBlock("event: ping")).toBeNull();
    expect(parseSseBlock("data: {oops")).toBeNull();
  });
});
