// Notification external store for useSyncExternalStore (no useEffect state setting)

let unreadCount = 0;
const listeners = new Set<() => void>();

export function setUnreadCount(count: number) {
  unreadCount = count;
  listeners.forEach((listener) => listener());
}

export function subscribeNotifications(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getUnreadSnapshot() {
  return unreadCount;
}

export function getUnreadServerSnapshot() {
  return 0;
}
