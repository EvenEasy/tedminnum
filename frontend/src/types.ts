export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "member";
  active: boolean;
  work_minutes: number;
  short_break: number;
  long_break: number;
  notifications: boolean;
}
export interface Client {
  id: string;
  name: string;
  rate?: string;
}
export interface Project {
  id: string;
  client_id: string;
  name: string;
  rate?: string | null;
  member_ids?: string[];
}
export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  due_date: string | null;
  estimate_minutes: number | null;
  position: number;
  billing: string;
  rate?: string | null;
  fixed_price?: string | null;
  version: number;
  assignee_ids: string[];
}
export interface Entry {
  id: string;
  user_id: string;
  task_id: string | null;
  kind: string;
  billable: boolean;
  started_at: string;
  ended_at: string | null;
  paused_at: string | null;
  paused_microseconds: number;
  seconds: number;
  note: string;
  reserved?: boolean;
  target_seconds: number;
}
export interface Line {
  id: string;
  description: string;
  quantity: string;
  rate: string;
  amount: string;
  source_entry_id: string | null;
  source_task_id: string | null;
  reserved: boolean;
}
export interface Payment {
  id: string;
  amount: string;
  currency: string;
  paid_on: string;
  reference: string;
}
export interface Invoice {
  id: string;
  client_id: string;
  client_name: string;
  number: string;
  status: string;
  total: string;
  currency: string;
  created_at: string;
  lines?: Line[];
  payments?: Payment[];
}
export interface Finance {
  currency: string;
  worked_estimate: string;
  uninvoiced_estimate: string;
  draft_reserved: string;
  outstanding: string;
  payments_received: string;
}
export interface Dashboard {
  work_seconds: number;
  break_seconds: number;
  open_tasks: number;
  tasks: Task[];
  recent: Entry[];
  finance: Finance | null;
}
export interface Audit {
  id: string;
  action: string;
  object_id: string;
  detail: string;
  created_at: string;
}
export interface Hook {
  id: string;
  url: string;
  enabled: boolean;
}
export interface Delivery {
  id: string;
  event: string;
  attempts: number;
  status_code: number | null;
  delivered_at: string | null;
  next_attempt: string;
}
export interface Workspace {
  name: string;
  currency: string;
}

export type Editor =
  | { kind: "client"; item?: Client }
  | { kind: "project"; item?: Project }
  | { kind: "task"; item?: Task }
  | { kind: "time"; item: Entry }
  | { kind: "invoice" }
  | { kind: "user" }
  | { kind: "reset"; item: User };
