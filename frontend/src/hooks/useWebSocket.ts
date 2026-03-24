import { useEffect, useRef, useState, useCallback } from 'react';
import { getToken } from './useAuth.ts';

type MessageHandler = (data: unknown) => void;

interface UseWebSocketOptions {
  url?: string;
  onMessage?: MessageHandler;
  reconnectInterval?: number;
  maxRetries?: number;
}

interface WebSocketState {
  isConnected: boolean;
  lastMessage: unknown | null;
  error: string | null;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    url = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws`,
    onMessage,
    reconnectInterval = 3000,
    maxRetries = 10,
  } = options;

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    lastMessage: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        // auth handshake
        ws.send(JSON.stringify({ type: 'auth', token }));
        setState(prev => ({ ...prev, isConnected: true, error: null }));
        retriesRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);
          setState(prev => ({ ...prev, lastMessage: data }));
          onMessageRef.current?.(data);
        } catch {
          // non-JSON message
        }
      };

      ws.onerror = () => {
        setState(prev => ({ ...prev, error: 'WebSocket error' }));
      };

      ws.onclose = () => {
        setState(prev => ({ ...prev, isConnected: false }));
        wsRef.current = null;

        if (retriesRef.current < maxRetries) {
          retriesRef.current += 1;
          reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
        }
      };
    } catch {
      setState(prev => ({ ...prev, error: 'Failed to connect' }));
    }
  }, [url, maxRetries, reconnectInterval]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    retriesRef.current = maxRetries; // prevent reconnect
    wsRef.current?.close();
  }, [maxRetries]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return { ...state, send, disconnect, reconnect: connect };
}
