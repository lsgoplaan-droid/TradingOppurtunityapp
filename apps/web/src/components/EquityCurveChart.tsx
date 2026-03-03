import { BacktestResult } from '../api/client';

interface Props {
  result: BacktestResult;
  height?: number;
}

export function EquityCurveChart({ result, height = 200 }: Props) {
  const { equityCurve } = result;

  if (!equityCurve || equityCurve.length === 0) {
    return <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No equity data</div>;
  }

  // SVG path generation for equity curve
  const values = equityCurve.map(p => p.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;
  const w = 600;
  const h = height;
  const pad = { top: 10, right: 10, bottom: 20, left: 60 };
  const innerW = w - pad.left - pad.right;
  const innerH = h - pad.top - pad.bottom;

  const toX = (i: number) => pad.left + (i / (values.length - 1)) * innerW;
  const toY = (v: number) => pad.top + innerH - ((v - minVal) / range) * innerH;

  const equityPath = values.map((v, i) =>
    `${i === 0 ? 'M' : 'L'} ${toX(i).toFixed(1)} ${toY(v).toFixed(1)}`
  ).join(' ');

  // Fill area under equity curve
  const fillPath = equityPath + ` L ${toX(values.length - 1).toFixed(1)} ${pad.top + innerH} L ${pad.left} ${pad.top + innerH} Z`;

  // Y-axis labels
  const yTicks = [minVal, (minVal + maxVal) / 2, maxVal];

  return (
    <div>
      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Equity Curve</div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }}>
        {/* Grid lines */}
        {yTicks.map((tick, i) => (
          <g key={i}>
            <line
              x1={pad.left} x2={w - pad.right}
              y1={toY(tick)} y2={toY(tick)}
              stroke="#e5e7eb" strokeWidth="1"
            />
            <text
              x={pad.left - 4} y={toY(tick) + 4}
              textAnchor="end" fontSize="10" fill="#9ca3af"
            >
              {tick >= 1000 ? `${(tick / 1000).toFixed(0)}k` : tick.toFixed(0)}
            </text>
          </g>
        ))}
        {/* Fill */}
        <path d={fillPath} fill="#3b82f6" opacity="0.1" />
        {/* Equity line */}
        <path d={equityPath} fill="none" stroke="#3b82f6" strokeWidth="1.5" />
      </svg>
    </div>
  );
}
