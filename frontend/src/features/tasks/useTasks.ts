import { useState } from "react";
import type { Mutation, Task } from "../../shared/types";
import { taskApi } from "./api";
export function useTasks(tasks: Task[], mutate: Mutation) {
  const [query, setQuery] = useState(""),
    [projectFilter, setProjectFilter] = useState(""),
    [board, setBoard] = useState(true);
  const moveTask = async (t: Task, status: string, position = t.position) =>
    mutate(
      () =>
        taskApi.update(t.id, {
          version: t.version,
          status,
          position,
        }),
      "Task moved",
    );
  const filteredTasks = tasks.filter(
    (t) =>
      (!projectFilter || t.project_id === projectFilter) &&
      t.title.toLowerCase().includes(query.toLowerCase()),
  );
  return {
    board,
    setBoard,
    query,
    setQuery,
    projectFilter,
    setProjectFilter,
    filteredTasks,
    moveTask,
  };
}
