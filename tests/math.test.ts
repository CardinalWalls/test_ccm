import { describe, expect, it } from "vitest";
import { add, subtract, divide, multiply, power } from "../src/math";

describe("math", () => {
  it("add", () => {
    expect(add(2, 3)).toBe(5);
  });

  it("subtract", () => {
    expect(subtract(5, 3)).toBe(2);
  });

  it("divide", () => {
    expect(divide(10, 2)).toBe(5);
  });

  it("divide by zero throws", () => {
    expect(() => divide(1, 0)).toThrow("Division by zero");
  });

  it("multiply", () => {
    expect(multiply(3, 4)).toBe(12);
  });

  it("power", () => {
    expect(power(2, 10)).toBe(1024);
  });
});
