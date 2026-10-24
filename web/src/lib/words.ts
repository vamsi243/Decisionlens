/** Plain-words strength of a change in probability, for fan views (no new numbers). */
export function swingWords(before: number, after: number): string {
  const d = after - before;
  if (d > 0.25) return "much more likely";
  if (d > 0.08) return "more likely";
  if (d >= -0.08) return "about as likely";
  if (d >= -0.25) return "less likely";
  return "much less likely";
}
