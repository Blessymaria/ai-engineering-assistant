/** 451.3 -> "7m 31s", 42 -> "42s" */
export function duration(seconds: number): string {
  const s = Math.round(seconds)
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`
}
