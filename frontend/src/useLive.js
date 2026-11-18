import { useEffect, useRef, useState } from "react";
import { wsUrl } from "./api";

/** WebSocket subscription with auto-reconnect. Calls onArticle for each newly analyzed article. */
export function useLive(onArticle) {
  const [status, setStatus] = useState("connecting");
  const handler = useRef(onArticle);
  handler.current = onArticle;

  useEffect(() => {
    let ws, timer, ping, closed = false, retry = 0;

    const connect = () => {
      setStatus("connecting");
      ws = new WebSocket(wsUrl());
      ws.onopen = () => {
        retry = 0;
        setStatus("live");
        ping = setInterval(() => ws.readyState === 1 && ws.send("ping"), 25000);
      };
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "article") handler.current(msg.data);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        clearInterval(ping);
        if (closed) return;
        setStatus("offline");
        timer = setTimeout(connect, Math.min(15000, 1000 * 2 ** retry++));
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      clearInterval(ping);
      ws && ws.close();
    };
  }, []);

  return status;
}
