export default function ClaimStages({ stage = 0, processing = false }) {
  return (
    <div className="stage-strip" aria-label="Claim workflow">
      {[
        ['Claim input', 'Product, issue & evidence'],
        ['AI analysis', 'Independent models & rules'],
        ['Decision', 'Recommendation & human review'],
      ].map(([name, description], i) => (
        <div
          className={`stage-item ${i === stage ? 'active' : ''} ${i === 1 && processing ? 'is-processing' : ''}`}
          aria-current={i === stage ? 'step' : undefined}
          key={name}
        >
          <span className="stage-number">{i === 1 && processing ? <span className="analysis-spinner" aria-label="Analysis in progress" /> : i + 1}</span>
          <div>
            <strong>{name}</strong>
            <small>{i === 1 && processing ? 'Analysis in progress…' : description}</small>
          </div>
        </div>
      ))}
    </div>
  );
}
