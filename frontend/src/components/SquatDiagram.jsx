export default function SquatDiagram() {
  return (
    <svg className="squat-diagram" viewBox="0 0 400 320" role="img" aria-labelledby="squat-diagram-title">
      <title id="squat-diagram-title">Side view of a squat at the bottom position</title>
      <line x1="60" y1="278" x2="280" y2="278" className="ground" />
      <circle cx="86" cy="64" r="15" className="plate" />
      <circle cx="196" cy="64" r="15" className="plate" />
      <line x1="86" y1="64" x2="196" y2="64" className="bar" />
      <circle cx="146" cy="46" r="13" className="body-line" fill="none" />
      <line x1="140" y1="66" x2="118" y2="136" className="body-line" />
      <line x1="118" y1="136" x2="188" y2="202" className="body-line" />
      <line x1="188" y1="202" x2="150" y2="272" className="body-line" />
      <line x1="118" y1="278" x2="196" y2="278" className="body-line" />
      <line x1="150" y1="272" x2="150" y2="278" className="body-line" />
      <circle cx="118" cy="136" r="4" className="joint" />
      <circle cx="188" cy="202" r="4" className="joint" />
      <line x1="118" y1="136" x2="300" y2="112" className="leader" />
      <text x="306" y="116" className="label">BACK</text>
      <text x="306" y="132" className="sublabel">angle</text>
      <line x1="118" y1="136" x2="300" y2="168" className="leader" />
      <text x="306" y="172" className="label">HIP</text>
      <text x="306" y="188" className="sublabel">angle</text>
      <line x1="188" y1="202" x2="300" y2="224" className="leader" />
      <text x="306" y="228" className="label">KNEE</text>
      <text x="306" y="244" className="sublabel">angle</text>
    </svg>
  )
}
