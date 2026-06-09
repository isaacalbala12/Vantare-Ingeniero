import React from "react";

interface HubCardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function HubCard({ title, children, className }: HubCardProps) {
  return (
    <section
      className={`relative rounded-[var(--radius-hub-card)] border border-hub-border bg-hub-card p-6 ${className ?? ""}`}
    >
      <div className="absolute left-0 top-4 bottom-4 w-[3px] rounded-full bg-a1-accent/70" />
      {title ? (
        <h2
          className="text-lg mb-4 text-a1-text pl-2"
          style={{ fontFamily: "var(--font-a1-display)" }}
        >
          {title}
        </h2>
      ) : null}
      <div className="pl-2">{children}</div>
    </section>
  );
}
