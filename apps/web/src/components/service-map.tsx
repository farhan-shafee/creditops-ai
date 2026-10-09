import { ArrowDown, ArrowRight, Box } from 'lucide-react';
import type { Incident, Topology } from '@/lib/types';
import { Status } from './primitives';

const levels = [
  ['rfq-gateway'],
  ['quote-service', 'execution-service'],
  ['pricing-service', 'risk-service', 'fix-gateway', 'audit-service'],
  ['market-data-service', 'reference-data-service', 'notification-service'],
];
export function ServiceMap({
  topology,
  incident,
  compact = false,
}: {
  topology: Topology | null;
  incident?: Incident | null;
  compact?: boolean;
}) {
  if (!topology) return <p className="muted padded">Loading service dependencies…</p>;
  const byName = new Map(topology.services.map((service) => [service.name, service]));
  return (
    <div className={`service-map ${compact ? 'compact-map' : ''}`}>
      <div className="map-legend">
        <Status value="healthy" />
        <Status value="degraded" />
        <Status value="suspected" />
        <Status value="impacted" />
      </div>
      <div className="map-levels">
        {levels.map((level, index) => (
          <div className="map-level" key={index}>
            {index > 0 && <ArrowDown className="map-arrow" size={18} aria-hidden />}
            <div className="map-row">
              {level.map((name) => {
                const service = byName.get(name);
                if (!service) return null;
                const affected = incident?.affected_services.includes(name);
                const status =
                  affected && service.status === 'healthy' ? 'impacted' : service.status;
                return (
                  <div className={`service-node ${affected ? 'node-affected' : ''}`} key={name}>
                    <div>
                      <Box size={14} aria-hidden />
                      <strong>{name}</strong>
                    </div>
                    <Status value={status} />
                    {!compact && <p>{service.description}</p>}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      {!compact && (
        <details className="dependency-list">
          <summary>Inspect {topology.dependencies.length} directed dependencies</summary>
          <div>
            {topology.dependencies.map((edge) => (
              <p key={`${edge.source}-${edge.target}`}>
                <code>{edge.source}</code>
                <ArrowRight size={12} aria-hidden />
                <code>{edge.target}</code>
              </p>
            ))}
          </div>
        </details>
      )}
      <p className="map-caption">
        Arrows indicate downstream dependency. Status reflects session telemetry; affected services
        are outlined.
      </p>
    </div>
  );
}
