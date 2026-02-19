import { describe, expect, it } from "vitest";
import { formatDate, daysBetween } from "../src/date-utils";

describe("date-utils", () => {
  describe("formatDate", () => {
    it("formats a normal date to YYYY-MM-DD", () => {
      const date = new Date("2023-05-15T10:30:00Z");
      expect(formatDate(date)).toBe("2023-05-15");
    });

    it("formats January 1st correctly", () => {
      const date = new Date("2023-01-01T00:00:00Z");
      expect(formatDate(date)).toBe("2023-01-01");
    });

    it("formats December 31st correctly", () => {
      const date = new Date("2023-12-31T23:59:59Z");
      expect(formatDate(date)).toBe("2023-12-31");
    });

    it("formats leap year date correctly", () => {
      const date = new Date("2024-02-29T12:00:00Z");
      expect(formatDate(date)).toBe("2024-02-29");
    });
  });

  describe("daysBetween", () => {
    it("returns 0 for the same date", () => {
      const date = new Date("2023-05-15T10:30:00Z");
      expect(daysBetween(date, date)).toBe(0);
    });

    it("calculates days between consecutive dates", () => {
      const date1 = new Date("2023-05-15T00:00:00Z");
      const date2 = new Date("2023-05-16T00:00:00Z");
      expect(daysBetween(date1, date2)).toBe(1);
    });

    it("calculates days between dates regardless of order", () => {
      const date1 = new Date("2023-05-15T00:00:00Z");
      const date2 = new Date("2023-05-20T00:00:00Z");
      expect(daysBetween(date1, date2)).toBe(5);
      expect(daysBetween(date2, date1)).toBe(5);
    });

    it("calculates days between dates spanning months", () => {
      const date1 = new Date("2023-04-30T00:00:00Z");
      const date2 = new Date("2023-05-02T00:00:00Z");
      expect(daysBetween(date1, date2)).toBe(2);
    });

    it("calculates days between dates spanning years", () => {
      const date1 = new Date("2022-12-31T00:00:00Z");
      const date2 = new Date("2023-01-02T00:00:00Z");
      expect(daysBetween(date1, date2)).toBe(2);
    });

    it("handles leap year correctly", () => {
      const date1 = new Date("2024-02-28T00:00:00Z");
      const date2 = new Date("2024-03-01T00:00:00Z");
      expect(daysBetween(date1, date2)).toBe(2);
    });
  });
});