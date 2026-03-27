export function add(a: number, b: number): number {
  return a + b;
}

export function subtract(a: number, b: number): number {
  return a - b;
}

export function divide(a: number, b: number): number {
  if (b === 0 && a !== 0) throw new Error("Division by zero");
  const result = a / b;
  if (!Number.isFinite(result)) throw new Error("Result is not finite");
  return result;
}

export function multiply(a: number, b: number): number {
  return a * b;
}

export function power(base: number, exponent: number): number {
  return Math.pow(base, exponent);
}

export function modulo(a: number, b: number): number {
  if (b === 0) throw new Error("Division by zero");
  return a % b;
}
