import { useCallback, useEffect, useRef } from "react";
import { api } from "../services/api";

export interface RealtimeMessage {
  room: string;
  event: string;
  data: Record<string, unknown>;
}

/**
 * Connects to the backend's realtime WebSocket, joins `room`, and invokes `onEvent`
 * for every broadcast received. Auto-reconnects with a short backoff and pings to keep
 * the socket alive. Returns a `broadcast` fn so this client can notify others of changes.
 */
export function useRealtime(room: string | null, onEvent: (msg: RealtimeMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!room) return;
    let closed = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let pingTimer: ReturnType<typeof setInterval>;

    const connect = () => {
      const url = api.realtimeUrl();
      if (!url) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ action: "join_room", room }));
        pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "ping" }));
          }
        }, 25000);
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg && msg.event) onEventRef.current(msg as RealtimeMessage);
        } catch {
          /* ignore non-JSON frames */
        }
      };

      ws.onclose = () => {
        clearInterval(pingTimer);
        if (!closed) reconnectTimer = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      closed = true;
      clearTimeout(reconnectTimer);
      clearInterval(pingTimer);
      wsRef.current?.close();
    };
  }, [room]);

  const broadcast = useCallback(
    (event: string, data: Record<string, unknown> = {}) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN && room) {
        ws.send(JSON.stringify({ action: "broadcast", room, event, data }));
      }
    },
    [room]
  );

  return { broadcast };
}
