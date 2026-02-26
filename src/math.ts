export function add(a: number, b: number): number {
  return a + b;
}

export function subtract(a: number, b: number): number {
  return a - b;
}

export function divide(a: number, b: number): number {
  const result = a / b;
  if (isNaN(result)) throw new Error("Division resulted in NaN");
  if (b === 0) throw new Error("Division by zero");
  return result;
}

export function remainder(a: number, b: number): number {
  if (b === 0) throw new Error("Division by zero");
  return ((a % b) + Math.abs(b)) % Math.abs(b);
}

export function multiply(a: number, b: number): number {
  return a * b;
}

export function power(base: number, exponent: number): number {
  return Math.pow(base, exponent);
}
