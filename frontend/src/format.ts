import type React from "react";
export const statuses = ["backlog", "in_progress", "done"];
export const label = (s: string) =>
  s.replaceAll("_", " ").replace(/^./, (v) => v.toUpperCase());
export const duration = (seconds: number) =>
  `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor((seconds % 3600) / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
export const dateTime = (s: string) => new Date(s).toLocaleString();
export const localInput = (s: string) => {
  const d = new Date(s);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 19);
};
export const today = () =>
  new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
export const formData = (e: React.FormEvent<HTMLFormElement>) =>
  new FormData(e.currentTarget);
export const text = (f: FormData, k: string) => String(f.get(k) || "");
export const nullable = (f: FormData, k: string) => text(f, k) || null;
export const checked = (f: FormData, k: string) => f.get(k) === "on";
