import type { ReactNode } from "react";

/**
 * Deliberate empty state: why the area is empty and what, if anything,
 * the technician can do next. Never invents content to look populated.
 */
export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon" aria-hidden="true">
        {icon}
      </span>
      <p className="empty-title">{title}</p>
      <p className="muted">{body}</p>
      {action}
    </div>
  );
}
