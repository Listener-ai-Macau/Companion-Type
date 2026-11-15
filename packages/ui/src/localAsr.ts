export function isLocalAsrProvider(provider: string | undefined): boolean {
  return provider === 'local-paraformer' || provider === 'local-meeting';
}
