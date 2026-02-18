export function unique<T>(arr: T[]): T[] {
  return [...new Set(arr)];
}

export function flatten<T>(arr: (T | T[])[]): T[] {
  return arr.flat() as T[];
}
