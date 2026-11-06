import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  clearCredentials,
  onUnauthorized,
  setCSRF,
  setIdentity,
} from "../../shared/apiClient";
import type { User } from "../../shared/types";
import { authApi } from "./api";
interface AuthState {
  user: User | null;
  initial: boolean;
  epoch: number;
  signIn: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clear: () => void;
  updateUser: (user: User) => void;
}
const AuthContext = createContext<AuthState | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null),
    [initial, setInitial] = useState(true),
    [epoch, setEpoch] = useState(0);
  const sessionEpoch = useRef(0);
  const clear = () => {
    sessionEpoch.current += 1;
    clearCredentials();
    setUser(null);
    setEpoch(sessionEpoch.current);
  };
  useEffect(() => {
    const abort = new AbortController();
    onUnauthorized(clear);
    authApi
      .me(abort.signal)
      .then((r) => {
        setCSRF(r.csrf);
        setIdentity(r.user.id);
        setUser(r.user);
      })
      .catch(() => {})
      .finally(() => {
        if (!abort.signal.aborted) setInitial(false);
      });
    return () => {
      abort.abort();
      onUnauthorized(null);
    };
  }, []);
  const signIn = async (email: string, password: string) => {
    sessionEpoch.current += 1;
    clearCredentials();
    const r = await authApi.login(email, password);
    setCSRF(r.csrf);
    setIdentity(r.user.id);
    setEpoch(sessionEpoch.current);
    setUser(r.user);
  };
  const logout = async () => {
    await authApi.logout();
    clear();
  };
  const updateUser = (replacement: User) => {
    if (sessionEpoch.current !== epoch) return;
    setUser((current) =>
      current?.id === replacement.id ? replacement : current,
    );
  };
  return (
    <AuthContext.Provider
      value={{
        user,
        initial,
        epoch,
        signIn,
        logout,
        clear,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("AuthProvider is required");
  return auth;
}
