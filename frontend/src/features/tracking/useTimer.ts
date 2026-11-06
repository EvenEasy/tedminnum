import { useCallback, useEffect, useRef, useState } from "react";
import type { Entry, User } from "../../shared/types";
import { trackingApi } from "./api";
export function useTimer(
  user: User,
  setNotice: (message: string) => void,
  setError: (message: string) => void,
) {
  const authEpoch = useRef(0),
    seenReminder = useRef(""),
    sequence = useRef(0);
  const [timer, setTimer] = useState<Entry | null>(null),
    [serverOffset, setServerOffset] = useState(0),
    [tick, setTick] = useState(Date.now()),
    [timerTask, setTimerTask] = useState(""),
    [timerKind, setTimerKind] = useState("work"),
    [timerBillable, setTimerBillable] = useState(true),
    [longBreak, setLongBreak] = useState(false);
  const refreshTimer = useCallback(async () => {
    const epoch = authEpoch.current,
      request = ++sequence.current;
    const r = await trackingApi.current();
    if (epoch !== authEpoch.current || request !== sequence.current) return;
    setTimer(r.entry);
    setServerOffset(new Date(r.server_time).getTime() - Date.now());
  }, []);
  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const elapsed = timer
    ? Math.max(
        0,
        Math.floor(
          ((timer.paused_at
            ? new Date(timer.paused_at).getTime()
            : tick + serverOffset) -
            new Date(timer.started_at).getTime() -
            timer.paused_microseconds / 1000) /
            1000,
        ),
      )
    : 0;
  useEffect(() => {
    if (
      timer &&
      !timer.paused_at &&
      elapsed >= timer.target_seconds &&
      seenReminder.current !== timer.id
    ) {
      seenReminder.current = timer.id;
      setNotice(
        timer.kind === "work"
          ? "Focus session complete. Stop work and take a break when ready."
          : "Break complete. Ready for another focus session?",
      );
      if (
        user?.notifications &&
        "Notification" in window &&
        Notification.permission === "granted"
      )
        new Notification("Tedminnum", {
          body:
            timer.kind === "work"
              ? "Time for a break."
              : "Your break is complete.",
        });
    }
  }, [elapsed, timer, user]);
  useEffect(() => {
    void refreshTimer().catch((e) => setError(e.message));
    const interval = setInterval(
      () => void refreshTimer().catch((e) => setError(e.message)),
      10000,
    );
    return () => {
      authEpoch.current += 1;
      clearInterval(interval);
    };
  }, [refreshTimer, setError]);
  return {
    timer,
    timerTask,
    setTimerTask,
    timerKind,
    setTimerKind,
    timerBillable,
    setTimerBillable,
    longBreak,
    setLongBreak,
    elapsed,
    refreshTimer,
  };
}
export type TimerState = ReturnType<typeof useTimer>;
