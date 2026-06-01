export default function AcquisitionProgressBar({ progress }) {
  if (!progress?.active && progress?.percent !== 100) return null;

  const percent = Math.min(100, Math.max(0, progress.percent ?? 0));

  return (
    <div
      className="acquisition-progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      aria-label={progress.message || 'Elaborazione immagini'}
    >
      <div className="acquisition-progress__header">
        <span className="acquisition-progress__message">{progress.message}</span>
        <span className="acquisition-progress__percent">{percent}%</span>
      </div>
      <div className="acquisition-progress__track">
        <div
          className="acquisition-progress__fill"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
