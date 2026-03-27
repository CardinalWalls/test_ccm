import { describe, expect, it } from "vitest";
import { add, subtract, divide, multiply, power, modulo } from "../src/math";

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

  it("divide with non-finite result throws", () => {
    expect(() => divide(Infinity, Infinity)).toThrow("Result is not finite");
    expect(() => divide(0, 0)).toThrow("Result is not finite");
  });

  it("multiply", () => {
    expect(multiply(3, 4)).toBe(12);
  });

  it("power", () => {
    expect(power(2, 10)).toBe(1024);
  });

  it("modulo", () => {
    expect(modulo(10, 3)).toBe(1);
    expect(modulo(15, 4)).toBe(3);
    expect(modulo(7, 7)).toBe(0);
  });

  it("modulo by zero throws", () => {
    expect(() => modulo(1, 0)).toThrow("Division by zero");
  });

  it("modulo with negative numbers", () => {
    expect(modulo(-10, 3)).toBe(-1);
    expect(modulo(10, -3)).toBe(1);
    expect(modulo(-10, -3)).toBe(-1);
  });
});
