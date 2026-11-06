import { useRef } from "react";
import { uid } from "../../shared/apiClient";
import type { Mutation } from "../../shared/types";
import { trackingApi } from "./api";
import type { TimerState } from "./useTimer";
export function useTimerActions(state: TimerState, mutate: Mutation) {
  const { timer, timerTask, timerKind, timerBillable, longBreak } = state;
  const timerKey = useRef(uid());
  const start = async (taskId?: string) => {
    if (
      await mutate(
        () =>
          trackingApi.start({
            request_key: timerKey.current,
            task_id: taskId || timerTask || null,
            kind: taskId ? "work" : timerKind,
            billable: timerBillable,
            long_break: longBreak,
          }),
        "Timer started",
      )
    )
      timerKey.current = uid();
  };
  const command = async (c: string) => {
    if (timer)
      await mutate(
        () => trackingApi.command(timer.id, c),
        c === "stop" ? "Session saved" : "Timer updated",
      );
  };
  return { start, command };
}
