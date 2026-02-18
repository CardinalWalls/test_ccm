import { describe, expect, it } from "vitest";
import { unique, flatten } from "../src/array-utils";

describe("unique", () => {
  it("removes duplicate numbers", () => {
    expect(unique([1, 2, 2, 3, 3, 3])).toEqual([1, 2, 3]);
  });

  it("removes duplicate strings", () => {
    expect(unique(["a", "b", "a", "c"])).toEqual(["a", "b", "c"]);
  });

  it("returns empty array for empty input", () => {
    expect(unique([])).toEqual([]);
  });

  it("returns same array when no duplicates", () => {
    expect(unique([1, 2, 3])).toEqual([1, 2, 3]);
  });

  it("handles all duplicates", () => {
    expect(unique([5, 5, 5])).toEqual([5]);
  });
});

describe("flatten", () => {
  it("flattens one level of nesting", () => {
    expect(flatten([[1, 2], [3, 4]])).toEqual([1, 2, 3, 4]);
  });

  it("handles mixed flat and nested", () => {
    expect(flatten([1, [2, 3], 4])).toEqual([1, 2, 3, 4]);
  });

  it("returns empty array for empty input", () => {
    expect(flatten([])).toEqual([]);
  });

  it("handles already flat array", () => {
    expect(flatten([1, 2, 3])).toEqual([1, 2, 3]);
  });

  it("handles array of strings", () => {
    expect(flatten([["a", "b"], ["c"]])).toEqual(["a", "b", "c"]);
  });
});
