"use client";

import { useEffect, useRef, useState } from "react";
import type { DashboardDelta } from "./types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/dashboard";

const INITIAL_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 8000;

export function useDashboardSocket(): { lastDelta: DashboardDelta | null; connected: boolean } {
  const [lastDelta, setLastDelta] = useState<DashboardDelta | null>(null);
  const [connected, setConnected] = useState(false);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const closedByUserRef = useRef(false);

  useEffect(() => {
    closedByUserRef.current = false;
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      socket = new WebSocket(WS_URL);

      socket.onopen = () => {
        setConnected(true);
        backoffRef.current = INITIAL_BACKOFF_MS;
      };

      socket.onmessage = (event) => {
        try {
          const delta = JSON.parse(event.data) as DashboardDelta;
          setLastDelta(delta);
        } catch {
          // ignore malformed payloads
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (closedByUserRef.current) return;
        retryTimer = setTimeout(connect, backoffRef.current);
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      };

      socket.onerror = () => {
        socket?.close();
      };
    }

    connect();

    return () => {
      closedByUserRef.current = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close();
    };
  }, []);

  return { lastDelta, connected };
}
