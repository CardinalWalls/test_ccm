import { describe, expect, it } from "vitest";
import { formatDate, daysBetween } from "../src/date-utils";

describe("date-utils", () => {
  describe("formatDate", () => {
    it("formats a regular date correctly", () => {
      const date = new Date(2023, 5, 15); // June 15, 2023
      expect(formatDate(date)).toBe("2023-06-15");
    });

    it("pads single-digit months and days with zeros", () => {
      const date = new Date(2023, 0, 5); // January 5, 2023
      expect(formatDate(date)).toBe("2023-01-05");
    });

    it("handles end of year dates", () => {
      const date = new Date(2023, 11, 31); // December 31, 2023
      expect(formatDate(date)).toBe("2023-12-31");
    });

    it("handles leap year dates", () => {
      const date = new Date(2024, 1, 29); // February 29, 2024
      expect(formatDate(date)).toBe("2024-02-29");
    });
  });

  describe("daysBetween", () => {
    it("returns 0 for the same date", () => {
      const date = new Date(2023, 5, 15);
      expect(daysBetween(date, date)).toBe(0);
    });

    it("calculates positive days between dates", () => {
      const date1 = new Date(2023, 5, 15); // June 15, 2023
      const date2 = new Date(2023, 5, 20); // June 20, 2023
      expect(daysBetween(date1, date2)).toBe(5);
    });

    it("calculates negative days when first date is later", () => {
      const date1 = new Date(2023, 5, 20); // June 20, 2023
      const date2 = new Date(2023, 5, 15); // June 15, 2023
      expect(daysBetween(date1, date2)).toBe(-5);
    });

    it("handles dates across months", () => {
      const date1 = new Date(2023, 4, 31); // May 31, 2023
      const date2 = new Date(2023, 5, 1);  // June 1, 2023
      expect(daysBetween(date1, date2)).toBe(1);
    });

    it("handles dates across years", () => {
      const date1 = new Date(2022, 11, 31); // December 31, 2022
      const date2 = new Date(2023, 0, 1);   // January 1, 2023
      expect(daysBetween(date1, date2)).toBe(1);
    });

    it("handles larger date differences", () => {
      const date1 = new Date(2023, 0, 1);   // January 1, 2023
      const date2 = new Date(2023, 11, 31); // December 31, 2023
      expect(daysBetween(date1, date2)).toBe(364);
    });
  });
});