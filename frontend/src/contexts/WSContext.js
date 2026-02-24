import React from "react";

const WSContext = React.createContext({ connected: false, unreadCount: 0, lastNotification: null });

export const WSProvider = ({ children }) => {
  const [connected, setConnected] = React.useState(false);
  const [unreadCount, setUnreadCount] = React.useState(0);
  const [lastNotification, setLastNotification] = React.useState(null);
  const [toasts, setToasts] = React.useState([]);
  const [wsStatus, setWsStatus] = React.useState("disconnected");
  const wsRef = React.useRef(null);
  const reconnectRef = React.useRef(null);
  const reconnectAttempts = React.useRef(0);
  const maxReconnectAttempts = 5;
  const intentionalClose = React.useRef(false);
  const connectedOnce = React.useRef(false);

  const addToast = React.useCallback((notification) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, ...notification }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  const connect = React.useCallback(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    if (wsRef.current) {
      intentionalClose.current = true;
      wsRef.current.close();
      wsRef.current = null;
    }
    intentionalClose.current = false;
    const backendUrl = process.env.REACT_APP_BACKEND_URL || "";
    const wsProtocol = backendUrl.startsWith("https") ? "wss" : "ws";
    const wsHost = backendUrl.replace(/^https?:\/\//, "").replace(/\/+$/, "");
    const wsUrl = `${wsProtocol}://${wsHost}/api/ws/notifications?token=${token}`;
    setWsStatus("connecting");
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => { setConnected(true); setWsStatus("connected"); reconnectAttempts.current = 0; connectedOnce.current = true; };
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "connected") { setConnected(true); setWsStatus("connected"); }
          else if (msg.type === "unread_count") { setUnreadCount(msg.data.count); }
          else if (msg.type === "notification") {
            setLastNotification(msg.data);
            setUnreadCount((prev) => prev + 1);
            addToast({ title: msg.data.title, message: msg.data.message, type: msg.data.type });
          }
        } catch {}
      };
      ws.onclose = () => {
        setConnected(false); wsRef.current = null;
        if (intentionalClose.current) { setWsStatus("disconnected"); return; }
        if (reconnectAttempts.current < maxReconnectAttempts) {
          setWsStatus("connecting");
          const delay = Math.min(2000 * Math.pow(1.5, reconnectAttempts.current), 30000);
          reconnectAttempts.current += 1;
          reconnectRef.current = setTimeout(() => { if (localStorage.getItem("token")) connect(); }, delay);
        } else { setWsStatus("failed"); }
      };
      ws.onerror = () => {};
    } catch { setWsStatus("failed"); }
  }, [addToast]);

  const disconnect = React.useCallback(() => {
    intentionalClose.current = true;
    if (reconnectRef.current) clearTimeout(reconnectRef.current);
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setConnected(false); setWsStatus("disconnected"); setUnreadCount(0); reconnectAttempts.current = 0;
  }, []);

  const sendMessage = React.useCallback((msg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(msg));
  }, []);

  const markRead = React.useCallback((notifId) => { sendMessage({ type: "mark_read", data: { notification_id: notifId } }); }, [sendMessage]);
  const markAllRead = React.useCallback(() => { sendMessage({ type: "mark_all_read" }); setUnreadCount(0); }, [sendMessage]);

  React.useEffect(() => {
    const interval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "ping" }));
    }, 25000);
    return () => clearInterval(interval);
  }, []);

  const toastContainer = toasts.length > 0 ? (
    <div className="ws-toast-container">
      {toasts.map((t) => (
        <div key={t.id} className="ws-toast" onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}>
          <div className="ws-toast-icon">{t.type === "request_received" ? "\ud83d\udccb" : t.type === "match_created" ? "\ud83e\udd1d" : t.type === "payment_completed" ? "\ud83d\udcb3" : "\ud83d\udd14"}</div>
          <div className="ws-toast-body"><div className="ws-toast-title">{t.title}</div><div className="ws-toast-msg">{t.message}</div></div>
          <button className="ws-toast-close" onClick={(e) => { e.stopPropagation(); setToasts((prev) => prev.filter((x) => x.id !== t.id)); }}>\u2715</button>
        </div>
      ))}
    </div>
  ) : null;

  return (
    <WSContext.Provider value={{ connected, unreadCount, lastNotification, connect, disconnect, markRead, markAllRead, setUnreadCount, wsStatus }}>
      {children}
      {toastContainer}
    </WSContext.Provider>
  );
};

export const useWS = () => React.useContext(WSContext);

export default WSContext;
