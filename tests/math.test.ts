import { describe, expect, it } from "vitest";
import { add, subtract, divide, multiply, power, sqrt, clamp } from "../src/math";

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

  it("sqrt", () => {
    expect(sqrt(9)).toBe(3);
    expect(sqrt(16)).toBe(4);
    expect(sqrt(0)).toBe(0);
    expect(sqrt(2)).toBeCloseTo(1.414, 3);
  });

  it("sqrt throws for negative numbers", () => {
    expect(() => sqrt(-1)).toThrow("Cannot calculate square root of negative number");
  });

  it("clamp", () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-5, 0, 10)).toBe(0);
    expect(clamp(15, 0, 10)).toBe(10);
    expect(clamp(0, 0, 10)).toBe(0);
    expect(clamp(10, 0, 10)).toBe(10);
  });

  it("clamp throws when min > max", () => {
    expect(() => clamp(5, 10, 0)).toThrow("min cannot be greater than max");
  });
});
