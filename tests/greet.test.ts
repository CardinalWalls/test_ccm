import { describe, it, expect } from "vitest";
import { greet, farewell } from "../src/greet";

describe("greet", () => {
  it("returns Hi, World! Welcome! for World", () => {
    expect(greet("World")).toBe("Hi, World! Welcome!");
  });

  it("returns Hi, Alice! Welcome! for Alice", () => {
    expect(greet("Alice")).toBe("Hi, Alice! Welcome!");
  });

  it("returns Hi, Bob! Welcome! for Bob", () => {
    expect(greet("Bob")).toBe("Hi, Bob! Welcome!");
  });
});

describe("farewell", () => {
  it("returns Goodbye, World! for World", () => {
    expect(farewell("World")).toBe("Goodbye, World!");
  });

  it("returns Goodbye, Alice! for Alice", () => {
    expect(farewell("Alice")).toBe("Goodbye, Alice!");
  });

  it("returns Goodbye, Bob! for Bob", () => {
    expect(farewell("Bob")).toBe("Goodbye, Bob!");
  });
});
