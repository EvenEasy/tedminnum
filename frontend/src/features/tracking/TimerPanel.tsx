import { duration } from "../../shared/format";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function TimerPanel(
  props: Pick<
    WorkspaceController,
    | "busy"
    | "command"
    | "elapsed"
    | "longBreak"
    | "setLongBreak"
    | "setTimerBillable"
    | "setTimerKind"
    | "setTimerTask"
    | "start"
    | "taskName"
    | "tasks"
    | "timer"
    | "timerBillable"
    | "timerKind"
    | "timerTask"
  >,
) {
  const {
    busy,
    command,
    elapsed,
    longBreak,
    setLongBreak,
    setTimerBillable,
    setTimerKind,
    setTimerTask,
    start,
    taskName,
    tasks,
    timer,
    timerBillable,
    timerKind,
    timerTask,
  } = props;

  return (
    <section
      className={`timer-panel ${timer ? "running" : ""}`}
      aria-label="Focus timer"
    >
      <div>
        <span className="eyebrow">
          {timer
            ? timer.kind === "break"
              ? "TAKE A BREATH"
              : "FOCUS IN PROGRESS"
            : "TIME FOR YOUR NEXT GOOD IDEA"}
        </span>
        <h2>
          {timer
            ? timer.kind === "break"
              ? "On a break"
              : taskName(timer.task_id)
            : "One thing at a time."}
        </h2>
        {timer ? (
          <span className="small muted">
            {timer.paused_at ? "Paused · " : ""}
            {Math.round(timer.target_seconds / 60)} minute reminder ·{" "}
            {timer.billable ? "Billable work" : "Non-billable"}
          </span>
        ) : (
          <div className="timer-options">
            <select
              aria-label="Timer task"
              value={timerTask}
              onChange={(e) => setTimerTask(e.target.value)}
            >
              <option value="">Work without a task</option>
              {tasks
                .filter((t) => t.status !== "done")
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
            </select>
            <select
              aria-label="Session type"
              value={timerKind}
              onChange={(e) => setTimerKind(e.target.value)}
            >
              <option value="work">Focus work</option>
              <option value="break">Break</option>
            </select>
            {timerKind === "work" ? (
              <label className="check small">
                <input
                  type="checkbox"
                  checked={timerBillable}
                  onChange={(e) => setTimerBillable(e.target.checked)}
                />
                Billable
              </label>
            ) : (
              <label className="check small">
                <input
                  type="checkbox"
                  checked={longBreak}
                  onChange={(e) => setLongBreak(e.target.checked)}
                />
                Long break
              </label>
            )}
          </div>
        )}
      </div>
      <div className="timer-controls">
        <div className="timer-value mono" aria-live="off">
          {duration(elapsed)}
        </div>
        {timer ? (
          <>
            <button
              disabled={busy}
              onClick={() => void command(timer.paused_at ? "resume" : "pause")}
            >
              {timer.paused_at ? "Resume" : "Pause"}
            </button>
            <button
              className="primary"
              disabled={busy}
              onClick={() => void command("stop")}
            >
              Stop & save
            </button>
          </>
        ) : (
          <button
            className="primary"
            disabled={busy}
            onClick={() => void start()}
          >
            ▶ Start session
          </button>
        )}
      </div>
    </section>
  );
}
