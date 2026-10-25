/** One background reader for cache notifications and active-view ticks.
 * Notifications carry no state or authority. A foreground action keeps its
 * own result; an invalidation during that action is read after it releases.
 */
export function createCachedRefresh<T>(options: {
  busy: () => boolean;
  epoch: () => number;
  read: () => Promise<T>;
  apply: (value: T) => void;
}) {
  let disposed = false;
  let dirty = false;
  let revision = 0;
  let flight: Promise<void> | null = null;
  const resume = (): Promise<void> => {
    if (disposed || !dirty || options.busy()) return flight ?? Promise.resolve();
    if (flight) return flight;
    // Defer so flight is assigned even if read rejects synchronously.
    flight = Promise.resolve().then(async () => {
      while (!disposed && dirty && !options.busy()) {
        dirty = false;
        const readRevision = revision;
        const epoch = options.epoch();
        try {
          const value = await options.read();
          if (!disposed && !options.busy() && epoch === options.epoch()
            && readRevision === revision) options.apply(value);
        } catch { /* Keep the last readable state; the next signal/tick can retry. */ }
      }
    }).finally(() => { flight = null; });
    return flight;
  };
  return {
    request(): Promise<void> {
      if (disposed) return Promise.resolve();
      dirty = true;
      revision += 1;
      return resume();
    },
    resume,
    dispose() { disposed = true; dirty = false; },
  };
}
