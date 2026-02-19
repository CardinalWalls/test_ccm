import { describe, it, expect } from "vitest";
import { greet } from "../src/greet";

describe("greet", () => {
  it("returns Hello, World! for World", () => {
    expect(greet("World")).toBe("Hello, World!");
  });
});
