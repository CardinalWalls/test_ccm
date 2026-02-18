import { describe, expect, it } from "vitest";
import { capitalize, reverse } from "../src/string-utils";

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
