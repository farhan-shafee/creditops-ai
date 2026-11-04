import { useRef, useState } from 'react';

export type GuidedRecordingStage = 'signal' | 'evidence' | 'proposal' | 'validation' | 'handoff';
const stages: readonly { id: GuidedRecordingStage; label: string; description: string }[] = [
  {
    id: 'signal',
    label: 'Signal',
    description: 'Read the recorded business observations, supported condition and cause status.',
  },
  {
    id: 'evidence',
    label: 'Evidence',
    description: 'Inspect discrete returned sources. Display filters do not change the recording.',
  },
  {
    id: 'proposal',
    label: 'Model proposal',
    description:
      'Follow explicit references from the original proposal, keeping unconfirmed claims visible.',
  },
  {
    id: 'validation',
    label: 'Validation',
    description:
      'Compare recorded fields and rule reasons. Normalization does not independently prove factual accuracy.',
  },
  {
    id: 'handoff',
    label: 'Handoff',
    description: 'Prepare a local draft for human review from the full recording.',
  },
];
export function GuidedRecordingReplay({
  onStep,
}: {
  onStep: (stage: GuidedRecordingStage | null) => void;
}) {
  const [index, setIndex] = useState<number | null>(null);
  const startButton = useRef<HTMLButtonElement>(null);
  const move = (next: number) => {
    setIndex(next);
    onStep(stages[next].id);
  };
  return (
    <section className="recording-guide" aria-label="Optional guided recording replay">
      <div className="recording-guide-intro">
        <h2>Walk through the recording</h2>
        <p>
          Five optional steps through existing recorded material. Progress changes only this view.
        </p>
      </div>
      {index === null ? (
        <button className="button secondary" ref={startButton} onClick={() => move(0)}>
          Start guided replay
        </button>
      ) : (
        <>
          <ol className="recording-guide-steps" aria-label="Guided replay progress">
            {stages.map((stage, position) => (
              <li key={stage.id} aria-current={position === index ? 'step' : undefined}>
                {stage.label}
              </li>
            ))}
          </ol>
          <p className="recording-guide-description" role="status">
            Step {index + 1} of {stages.length} · {stages[index].label}: {stages[index].description}
          </p>
          <div className="recording-guide-actions">
            <button
              className="button secondary"
              disabled={index === 0}
              onClick={() => move(index - 1)}
            >
              Previous
            </button>
            <button
              className="button primary"
              disabled={index === stages.length - 1}
              onClick={() => move(index + 1)}
            >
              Next
            </button>
            <button
              className="button secondary"
              onClick={() => {
                setIndex(null);
                onStep(null);
                requestAnimationFrame(() => startButton.current?.focus());
              }}
            >
              Exit guided replay
            </button>
          </div>
        </>
      )}
    </section>
  );
}
