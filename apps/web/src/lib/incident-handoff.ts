export type HandoffTemplate = 'technical' | 'stakeholder';
export type HandoffSection = {
  heading: string;
  paragraphs: readonly string[];
  evidenceIds: readonly string[];
};
export type HandoffSource = {
  id: string;
  kind: string;
  service: string;
  timestamp: string;
  detail: string;
};
export type HandoffDraft = {
  template: HandoffTemplate;
  incidentId: string;
  preparedAt: string;
  labels: readonly string[];
  sections: readonly HandoffSection[];
  sources: readonly HandoffSource[];
  pinnedSourceIds: readonly string[];
  unavailableSourceIds: readonly string[];
};
