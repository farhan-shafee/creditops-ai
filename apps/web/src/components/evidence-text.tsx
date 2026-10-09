export function EvidenceText({
  text,
  onEvidence,
}: {
  text: string;
  onEvidence: (id: string) => void;
}) {
  const parts = text.split(
    /(\b(?:LOG|METRIC|DEPLOY|INC-HIST|RUNBOOK|FIX|KAFKA|DB|BUSINESS|INCIDENT|TOPOLOGY|TOPO|EVID|HIST|INC-DEMO)-(?:[A-Z0-9_]+-)*[A-Z0-9_]+\b)/g,
  );
  return (
    <span>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <button className="citation" key={`${part}-${index}`} onClick={() => onEvidence(part)}>
            {part}
          </button>
        ) : (
          part
        ),
      )}
    </span>
  );
}
