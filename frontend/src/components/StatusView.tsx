import type { ReactNode } from "react";

type StatusViewProps = {
  title: string;
  detail: string;
  action?: ReactNode;
  tone?: "neutral" | "error";
};

export function StatusView({
  title,
  detail,
  action,
  tone = "neutral",
}: StatusViewProps) {
  return (
    <section className={`status-card ${tone === "error" ? "is-error" : ""}`}>
      <div className="status-dot" />
      <div className="status-copy">
        <h2>{title}</h2>
        <p>{detail}</p>
      </div>
      {action ? <div className="status-action">{action}</div> : null}
    </section>
  );
}
