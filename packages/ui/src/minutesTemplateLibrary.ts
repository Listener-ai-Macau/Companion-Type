import type { CompanionV1HostSession, CompanionV1MinutesVariant } from '@companion-type/core';

export interface SavedCustomMinutesTemplate { name: string; instructions: string }

/** Reuse exact custom template versions already saved inside meeting results. */
export function savedCustomMinutesTemplates(sessions: readonly CompanionV1HostSession[]): SavedCustomMinutesTemplate[] {
  const found: SavedCustomMinutesTemplate[] = [];
  const seen = new Set<string>();
  for (const session of sessions) {
    if (session.organization?.trashedAt) continue;
    const variants: (CompanionV1MinutesVariant | null | undefined)[] = [
      session.minutesByMode?.offlineStore,
      session.minutesByMode?.onlineLive,
      ...(session.minutesByMode?.history ?? []).map(item => item.variant),
    ];
    for (const variant of variants) {
      const value = variant?.template;
      if (value?.id !== 'custom' || typeof value.name !== 'string' || typeof value.instructions !== 'string') continue;
      const name = value.name.trim();
      const instructions = value.instructions.trim();
      if (!name || !instructions) continue;
      const key = JSON.stringify([name, instructions]);
      if (seen.has(key)) continue;
      seen.add(key);
      found.push({ name, instructions });
    }
  }
  return found;
}
