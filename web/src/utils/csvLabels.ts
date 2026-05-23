/** 拆分逗号 / 中文逗号分隔的标签或人名 */
export function splitLabels(raw: string | null | undefined): string[] {
  if (!raw?.trim()) return [];
  return raw
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean);
}
