import { api } from "./api";
import type { ClosureRequest, FieldPacket } from "./types";

const QUEUE_KEY = "field-closure-queue";

export interface QueuedClosure {
  eventId: string;
  request: ClosureRequest;
  queuedAt: string;
}

export function readQueue(): QueuedClosure[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeQueue(queue: QueuedClosure[]): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}

export function enqueueClosure(eventId: string, request: ClosureRequest): void {
  const queue = readQueue();
  queue.push({ eventId, request, queuedAt: new Date().toISOString() });
  writeQueue(queue);
}

/** Attempts to sync every queued closure; entries that still fail stay queued. */
export async function drainQueue(): Promise<{ synced: number; remaining: number }> {
  const queue = readQueue();
  if (queue.length === 0) return { synced: 0, remaining: 0 };

  const stillQueued: QueuedClosure[] = [];
  let synced = 0;
  for (const item of queue) {
    try {
      await api.fieldClose(item.eventId, item.request);
      synced += 1;
    } catch {
      stillQueued.push(item);
    }
  }
  writeQueue(stillQueued);
  return { synced, remaining: stillQueued.length };
}

const PACKET_CACHE_PREFIX = "field-packet-cache-";

export function cachePacket(recommendationId: string, packet: FieldPacket): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(`${PACKET_CACHE_PREFIX}${recommendationId}`, JSON.stringify(packet));
  } catch {
    // storage full or unavailable — caching is best-effort, not load-bearing
  }
}

export function readCachedPacket(recommendationId: string): FieldPacket | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(`${PACKET_CACHE_PREFIX}${recommendationId}`);
    return raw ? (JSON.parse(raw) as FieldPacket) : null;
  } catch {
    return null;
  }
}
