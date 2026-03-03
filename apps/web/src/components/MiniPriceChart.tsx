interface Props {
  candles: { t: number; c: number }[];
  support?: number[];
  resistance?: number[];
  entryPrice?: number;
}

export function MiniPriceChart({ candles, support = [], resistance = [], entryPrice }: Props) {
  if (!candles || candles.length < 2) return null;

  const W = 280;
  const H = 110;
  const PAD_X = 4;
  const PAD_Y = 8;

  const closes = candles.map(c => c.c);
  const allPrices = [...closes, ...support, ...resistance];
  const minP = Math.min(...allPrices) * 0.998;
  const maxP = Math.max(...allPrices) * 1.002;
  const range = maxP - minP || 1;

  const px = (i: number) =>
    PAD_X + (i / (closes.length - 1)) * (W - 2 * PAD_X);
  const py = (price: number) =>
    PAD_Y + (1 - (price - minP) / range) * (H - 2 * PAD_Y);

  const linePoints = closes.map((c, i) => `${px(i)},${py(c)}`).join(' ');
  const areaPoints = `${px(0)},${H - PAD_Y} ${linePoints} ${px(closes.length - 1)},${H - PAD_Y}`;

  const last = closes[closes.length - 1];
  const first = closes[0];
  const isUp = last >= first;
  const lineColor = isUp ? '#22c55e' : '#ef4444';
  const fillId = `fill-${Math.random().toString(36).slice(2)}`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      style={{ height: H }}
    >
      <defs>
        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.18" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Area fill */}
      <polygon points={areaPoints} fill={`url(#${fillId})`} />

      {/* Support lines */}
      {support.map((s, i) => (
        <g key={`s${i}`}>
          <line
            x1={PAD_X} y1={py(s)} x2={W - PAD_X} y2={py(s)}
            stroke="#22c55e" strokeWidth="1" strokeDasharray="4,3" opacity="0.75"
          />
          <text x={W - PAD_X - 2} y={py(s) - 2} fontSize="8" fill="#22c55e" textAnchor="end">
            {s.toFixed(s > 99 ? 0 : 2)}
          </text>
        </g>
      ))}

      {/* Resistance lines */}
      {resistance.map((r, i) => (
        <g key={`r${i}`}>
          <line
            x1={PAD_X} y1={py(r)} x2={W - PAD_X} y2={py(r)}
            stroke="#ef4444" strokeWidth="1" strokeDasharray="4,3" opacity="0.75"
          />
          <text x={W - PAD_X - 2} y={py(r) - 2} fontSize="8" fill="#ef4444" textAnchor="end">
            {r.toFixed(r > 99 ? 0 : 2)}
          </text>
        </g>
      ))}

      {/* Price line */}
      <polyline points={linePoints} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinejoin="round" />

      {/* Entry price dot + label */}
      {entryPrice != null && (
        <g>
          <circle
            cx={px(closes.length - 1)}
            cy={py(entryPrice)}
            r="3.5"
            fill={lineColor}
            stroke="white"
            strokeWidth="1"
          />
        </g>
      )}
    </svg>
  );
}
