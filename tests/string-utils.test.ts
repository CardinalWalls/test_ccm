import { describe, expect, it } from "vitest";
import { capitalize, reverse, truncate, padLeft } from "../src/string-utils";

describe("capitalize", () => {
  it("capitalizes first letter and lowercases rest", () => {
    expect(capitalize("hello")).toBe("Hello");
  });

  it("handles already capitalized string", () => {
    expect(capitalize("WORLD")).toBe("World");
  });

  it("handles empty string", () => {
    expect(capitalize("")).toBe("");
  });

  it("handles single character", () => {
    expect(capitalize("a")).toBe("A");
  });
});

describe("reverse", () => {
  it("reverses a string", () => {
    expect(reverse("hello")).toBe("olleh");
  });

  it("handles empty string", () => {
    expect(reverse("")).toBe("");
  });

  it("handles palindrome", () => {
    expect(reverse("racecar")).toBe("racecar");
  });

  it("handles single character", () => {
    expect(reverse("a")).toBe("a");
  });
});

describe("truncate", () => {
  it("truncates string to max length", () => {
    expect(truncate("hello world", 5)).toBe("hello");
  });

  it("returns original string if shorter than max length", () => {
    expect(truncate("hi", 5)).toBe("hi");
  });

  it("returns original string if equal to max length", () => {
    expect(truncate("hello", 5)).toBe("hello");
  });

  it("handles empty string", () => {
    expect(truncate("", 5)).toBe("");
  });

  it("handles zero max length", () => {
    expect(truncate("hello", 0)).toBe("");
  });

  it("handles negative max length", () => {
    expect(truncate("hello", -1)).toBe("");
  });

  it("handles null/undefined string", () => {
    expect(truncate(null as any, 5)).toBe("");
    expect(truncate(undefined as any, 5)).toBe("");
  });
});

describe("padLeft", () => {
  it("pads string with spaces by default", () => {
    expect(padLeft("hi", 5, " ")).toBe("   hi");
  });

  it("pads string with specified character", () => {
    expect(padLeft("123", 6, "0")).toBe("000123");
  });

  it("returns original string if already at target length", () => {
    expect(padLeft("hello", 5, "x")).toBe("hello");
  });

  it("returns original string if longer than target length", () => {
    expect(padLeft("hello world", 5, "x")).toBe("hello world");
  });

  it("handles empty string", () => {
    expect(padLeft("", 3, "x")).toBe("xxx");
  });

  it("handles null/undefined string", () => {
    expect(padLeft(null as any, 3, "x")).toBe("xxx");
    expect(padLeft(undefined as any, 3, "x")).toBe("xxx");
  });

  it("handles empty pad character", () => {
    expect(padLeft("hi", 5, "")).toBe("hi");
  });

  it("handles single character padding", () => {
    expect(padLeft("a", 4, "*")).toBe("***a");
  });
});
