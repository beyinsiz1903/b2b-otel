import React from "react";
import { Navigate } from "react-router-dom";
import axios, { getToken, setToken, clearToken } from "@/utils/api";
import { useWS } from "./WSContext";

const AuthContext = React.createContext(null);

export const AuthProvider = ({ children }) => {
  const [hotel, setHotel] = React.useState(null);
  const ws = useWS();

  const loadMe = async () => {
    if (!getToken()) return;
    try {
      const res = await axios.get("/auth/me");
      setHotel(res.data);
    } catch {
      clearToken();
      setHotel(null);
    }
  };

  React.useEffect(() => {
    loadMe();
    if (getToken()) ws.connect();
    return () => ws.disconnect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = async (email, password) => {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    const res = await axios.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    setToken(res.data.access_token);
    await loadMe();
    ws.connect();
  };

  const logout = () => {
    ws.disconnect();
    clearToken();
    setHotel(null);
  };

  return (
    <AuthContext.Provider value={{ hotel, login, logout, reload: loadMe }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => React.useContext(AuthContext);

export const ProtectedRoute = ({ children }) => {
  const { hotel } = useAuth();
  if (!getToken()) return <Navigate to="/login" replace />;
  if (!hotel) return <div className="page-center"><span className="loading-spin" /></div>;
  return children;
};

export default AuthContext;
