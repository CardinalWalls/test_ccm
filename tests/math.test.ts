import { describe, expect, it } from "vitest";
import { add } from "../src/math";

describe("math", () => {
  it("add", () => {
    expect(add(2, 3)).toBe(5);
  });
});
