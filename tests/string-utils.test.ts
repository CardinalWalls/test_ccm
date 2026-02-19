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
  it("truncates string to maximum length", () => {
    expect(truncate("hello world", 5)).toBe("hello");
  });

  it("returns original string if shorter than maxLen", () => {
    expect(truncate("hi", 5)).toBe("hi");
  });

  it("returns original string if equal to maxLen", () => {
    expect(truncate("hello", 5)).toBe("hello");
  });

  it("handles empty string", () => {
    expect(truncate("", 5)).toBe("");
  });

  it("handles maxLen of 0", () => {
    expect(truncate("hello", 0)).toBe("");
  });

  it("handles negative maxLen", () => {
    expect(truncate("hello", -1)).toBe("");
  });

  it("handles single character truncation", () => {
    expect(truncate("hello", 1)).toBe("h");
  });
});

describe("padLeft", () => {
  it("pads string on the left with spaces by default", () => {
    expect(padLeft("hi", 5)).toBe("   hi");
  });

  it("pads string on the left with specified character", () => {
    expect(padLeft("hi", 5, "0")).toBe("000hi");
  });

  it("returns original string if length is equal", () => {
    expect(padLeft("hello", 5)).toBe("hello");
  });

  it("returns original string if length is shorter", () => {
    expect(padLeft("hello", 3)).toBe("hello");
  });

  it("handles empty string", () => {
    expect(padLeft("", 3)).toBe("   ");
  });

  it("handles empty string with custom character", () => {
    expect(padLeft("", 3, "x")).toBe("xxx");
  });

  it("handles single character padding", () => {
    expect(padLeft("a", 3)).toBe("  a");
  });

  it("handles zero length", () => {
    expect(padLeft("hello", 0)).toBe("hello");
  });
});
