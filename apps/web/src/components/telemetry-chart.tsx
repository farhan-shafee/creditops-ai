import { useId } from 'react';
import type { MetricSeries } from '@/lib/types';
import { time } from './primitives';

export function TelemetryChart({
  series,
  onEvidence,
  color = 'teal',
}: {
  series?: MetricSeries;
  onEvidence: (id: string) => void;
  color?: 'teal' | 'amber';
}) {
  const id = useId().replaceAll(':', '');
  const points = series?.points ?? [];
  if (!series || !points.length)
    return (
      <div className="chart-empty">
        Telemetry samples will appear as the simulated clock advances.
      </div>
    );
  const width = 580,
    height = 176,
    left = 42,
    right = 12,
    top = 16,
    bottom = 26;
  const max = Math.max(...points.map((point) => point.value), 1) * 1.18;
  const plotHeight = height - top - bottom;
  const coordinates = points.map((point, index) => ({
    x: left + (index / Math.max(points.length - 1, 1)) * (width - left - right),
    y: top + plotHeight * (1 - point.value / max),
    point,
  }));
  const line = coordinates
    .map(({ x, y }, index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ');
  const area = `${line} L${coordinates.at(-1)!.x},${height - bottom} L${left},${height - bottom} Z`;
  const current = points.at(-1)!.value;
  return (
    <div className={`telemetry-chart chart-${color}`}>
      <div className="chart-label">
        <span>
          {series.service} <span className="muted">/ {series.metric.replaceAll('_', ' ')}</span>
        </span>
        <strong>
          {current.toLocaleString('en-US', { maximumFractionDigits: 1 })}
          <small>{series.unit}</small>
        </strong>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${series.metric} for ${series.service}: ${points.length} samples, latest ${current} ${series.unit}`}
      >
        <defs>
          <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.2" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 0.5, 1].map((fraction) => (
          <g key={fraction}>
            <line
              x1={left}
              x2={width - right}
              y1={top + plotHeight * fraction}
              y2={top + plotHeight * fraction}
              className="chart-grid"
            />
            <text x={left - 7} y={top + plotHeight * fraction + 3} textAnchor="end">
              {Math.round(max * (1 - fraction)).toLocaleString()}
            </text>
          </g>
        ))}
        <path d={area} fill={`url(#${id})`} />
        <path d={line} fill="none" stroke="currentColor" strokeWidth="2.2" />
        {coordinates.map(({ x, y, point }, index) => (
          <circle
            key={`${point.evidence_id}-${index}`}
            cx={x}
            cy={y}
            r={index === points.length - 1 ? 4 : 2.8}
            fill="currentColor"
            role="button"
            tabIndex={0}
            aria-label={`Inspect ${point.evidence_id}: ${point.value} ${series.unit}`}
            onClick={() => onEvidence(point.evidence_id)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onEvidence(point.evidence_id);
              }
            }}
          >
            <title>
              {time(point.timestamp)} UTC · {point.value} {series.unit} · {point.evidence_id}
            </title>
          </circle>
        ))}
        <text x={left} y={height - 5}>
          {time(points[0].timestamp)}
        </text>
        <text x={width - right} y={height - 5} textAnchor="end">
          {time(points.at(-1)!.timestamp)} UTC
        </text>
      </svg>
      <details className="chart-data">
        <summary>Inspect accessible sample data</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>UTC time</th>
                <th>Value ({series.unit})</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point, index) => (
                <tr key={index}>
                  <td>{time(point.timestamp)}</td>
                  <td>{point.value}</td>
                  <td>
                    <button className="citation" onClick={() => onEvidence(point.evidence_id)}>
                      {point.evidence_id}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
