export function capitalize(str: string): string {
  if (!str) return str;
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

export function reverse(str: string): string {
  return str.split("").reverse().join("");
}

export function truncate(str: string, maxLen: number): string {
  if (!str || maxLen <= 0) return "";
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen);
}

export function padLeft(str: string, len: number, char: string): string {
  if (!str) str = "";
  if (len <= str.length) return str;
  if (!char) return str;
  const padLength = len - str.length;
  return char.repeat(padLength) + str;
}
