export function add(a: number, b: number): number {
  return a + b;
}

export function subtract(a: number, b: number): number {
  return a - b;
}

export function divide(a: number, b: number): number {
  if (b === 0) throw new Error("Division by zero");
  return a / b;
}

export function multiply(a: number, b: number): number {
  return a * b;
}

export function power(base: number, exponent: number): number {
  return Math.pow(base, exponent);
}

export function sqrt(x: number): number {
  if (x < 0) throw new Error("Cannot calculate square root of negative number");
  return Math.sqrt(x);
}

export function clamp(x: number, min: number, max: number): number {
  if (min > max) throw new Error("min cannot be greater than max");
  return Math.min(Math.max(x, min), max);
}
