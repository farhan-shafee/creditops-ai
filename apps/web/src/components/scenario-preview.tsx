import { FileText, Search, ShieldCheck } from 'lucide-react';
import type { Scenario } from '@/lib/types';
export function ScenarioPreview({
  scenario,
  fallbackTitle,
  state,
}: {
  scenario?: Scenario;
  fallbackTitle: string;
  state: 'unloaded' | 'loading' | 'restoring';
}) {
  return (
    <div className="scenario-preview" data-testid="scenario-preview">
      <div className="scenario-preview-heading">
        <FileText size={24} aria-hidden />
        <div>
          <span className="eyebrow">Selected scenario · synthetic recording</span>
          <h3>{scenario?.title ?? fallbackTitle}</h3>
        </div>
      </div>
      <p>
        {scenario?.description ??
          'Scenario metadata unavailable. The requested recording will not be replaced with another scenario.'}
      </p>
      <dl>
        <div>
          <dt>Incident reference</dt>
          <dd className="mono">{scenario?.incident_id ?? 'Not available'}</dd>
        </div>
        <div>
          <dt>Recording state</dt>
          <dd>
            {state === 'loading'
              ? 'Loading selected recording…'
              : state === 'restoring'
                ? 'Restoring selected recording…'
                : 'Selected recording is not loaded'}
          </dd>
        </div>
      </dl>
      <div className="scenario-preview-path">
        <span>
          <Search size={16} aria-hidden /> Frozen evidence
        </span>
        <span>
          <FileText size={16} aria-hidden /> Original proposal & recorded validation
        </span>
        <span>
          <ShieldCheck size={16} aria-hidden /> Human-review handoff
        </span>
      </div>
      <p className="scenario-preview-note">
        {state === 'unloaded'
          ? 'Choose View recorded investigation to load this scenario. Changing the selection does not start an investigation.'
          : 'Waiting for the matching recorded investigation. Current simulation evidence is not substituted.'}
      </p>
    </div>
  );
}
