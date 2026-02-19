export function formatDate(date: Date): string {
  return date.toISOString().split('T')[0];
}

export function daysBetween(a: Date, b: Date): number {
  const msPerDay = 24 * 60 * 60 * 1000;
  return Math.abs(Math.floor((b.getTime() - a.getTime()) / msPerDay));
}