import { ArrowUpRight, LoaderCircle, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return (
    <span className={`badge badge-${tone}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}
export function Status({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const tone = /healthy|connected|complete|normal|resolved/.test(normalized)
    ? 'teal'
    : /degraded|warning|investigating|suspected/.test(normalized)
      ? 'amber'
      : /impacted|critical|error|disconnected|failed/.test(normalized)
        ? 'red'
        : 'neutral';
  return <Badge tone={tone}>{value.replaceAll('_', ' ')}</Badge>;
}
export function Panel({
  title,
  eyebrow,
  action,
  children,
  className = '',
}: {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <ShieldCheck size={28} strokeWidth={1.4} />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}
export function Spinner() {
  return <LoaderCircle size={16} className="spin" aria-hidden />;
}
export function Citation({ id, onEvidence }: { id: string; onEvidence: (id: string) => void }) {
  return (
    <button className="citation" onClick={() => onEvidence(id)}>
      {id}
      <ArrowUpRight size={10} aria-hidden />
    </button>
  );
}
export function time(value: string): string {
  return new Date(value).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: 'UTC',
    hour12: false,
  });
}
export function percent(value: number): string {
  return `${(value <= 1 ? value * 100 : value).toFixed(0)}%`;
}
