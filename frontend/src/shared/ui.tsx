import React, { useEffect, useId, useRef } from "react";
import { label } from "./format";
export function ErrorMessage({ error }: { error: string }) {
  return error ? (
    <div className="alert error" role="alert">
      {error}
    </div>
  ) : null;
}
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}
export function Field({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const generatedId = useId();
  const child = React.isValidElement<{ id?: string }>(children)
    ? children
    : null;
  const id = child?.props.id || generatedId;
  return (
    <div className="field">
      <label htmlFor={id}>{title}</label>
      {child ? React.cloneElement(child, { id }) : children}
    </div>
  );
}

export function Status({ value }: { value: string }) {
  return <span className={`badge ${value}`}>{label(value)}</span>;
}
export function Money({
  value,
  currency,
}: {
  value: string;
  currency: string;
}) {
  return (
    <>
      {new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
        Number(value),
      )}
    </>
  );
}
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      aria-label={title}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button
          type="button"
          className="icon"
          aria-label="Close dialog"
          onClick={onClose}
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  );
}
