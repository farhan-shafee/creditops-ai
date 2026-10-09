export function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
export function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* Persistence is optional when browser storage is disabled. */
  }
}
export function removeStorage(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* The in-memory view still resets. */
  }
}
