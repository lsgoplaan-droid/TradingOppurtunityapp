import { BacktestResult, Trade } from '../api/client';

interface Props {
  result: BacktestResult;
  height?: number;
  selectedTrade?: Trade | null;
}

const W = 600;
const PAD = { top: 10, right: 10, bottom: 20, left: 60 };
const INNER_W = W - PAD.left - PAD.right;

function svgPath(values: number[], innerH: number, minVal: number, range: number, offsetY: number): string {
  return values.map((v, i) => {
    const x = PAD.left + (i / Math.max(values.length - 1, 1)) * INNER_W;
    const y = offsetY + innerH - ((v - minVal) / (range || 1)) * innerH;
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');
}

export function EquityCurveChart({ result, height = 200, selectedTrade }: Props) {
  const { equityCurve, drawdownCurve, trades } = result;

  if (!equityCurve || equityCurve.length === 0) {
    return <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No equity data</div>;
  }

  // ── Equity curve ──────────────────────────────────────────────────────────
  const eqValues = equityCurve.map(p => p.value);
  const eqMin    = Math.min(...eqValues);
  const eqMax    = Math.max(...eqValues);
  const eqRange  = eqMax - eqMin || 1;
  const eqInnerH = height - PAD.top - PAD.bottom;

  const eqPath   = svgPath(eqValues, eqInnerH, eqMin, eqRange, PAD.top);
  const fillPath = eqPath + ` L ${(PAD.left + INNER_W).toFixed(1)} ${PAD.top + eqInnerH} L ${PAD.left} ${PAD.top + eqInnerH} Z`;
  const yTicks   = [eqMin, (eqMin + eqMax) / 2, eqMax];

  // ── Drawdown pane ─────────────────────────────────────────────────────────
  const DD_H     = 72;
  const DD_INNER = DD_H - 8 - 18; // top/bottom pad
  const hasDd    = !!drawdownCurve && drawdownCurve.length > 1;
  const ddValues = hasDd ? drawdownCurve!.map(p => p.value) : [];
  const ddMin    = hasDd ? Math.min(...ddValues) : -0.01;
  const ddRange  = Math.abs(ddMin) || 0.01;

  const ddPath = hasDd ? svgPath(ddValues, DD_INNER, ddMin, ddRange, 8).replace(
    // shift y from drawdown scale (0=top, ddMin=bottom)
    // svgPath uses offsetY=8 with minVal=ddMin already, but ddMin is negative, so min → bottom
    // We need: 0 → top (y=8), ddMin → y=8+DD_INNER
    // With the helper: y = 8 + DD_INNER - ((v - ddMin) / ddRange) * DD_INNER
    // When v=0: y = 8 + DD_INNER - (DD_INNER) = 8  ✓ (0 drawdown at top)
    // When v=ddMin: y = 8 + DD_INNER ✓
    //, /,
  ) : '';
  const ddFill = hasDd ? ddPath + ` L ${(PAD.left + INNER_W).toFixed(1)} ${8} L ${PAD.left} ${8} Z` : '';

  // ── Selected-trade vertical lines ─────────────────────────────────────────
  let entryX: number | null = null;
  let exitX:  number | null = null;
  if (selectedTrade && equityCurve.length > 1) {
    const tsStart = equityCurve[0].timestamp;
    const tsEnd   = equityCurve[equityCurve.length - 1].timestamp;
    const span    = tsEnd - tsStart || 1;
    entryX = PAD.left + ((new Date(selectedTrade.entryDate).getTime() - tsStart) / span) * INNER_W;
    exitX  = PAD.left + ((new Date(selectedTrade.exitDate).getTime()  - tsStart) / span) * INNER_W;
  }

  // ── Win/loss dots on equity curve ─────────────────────────────────────────
  const dots: { x: number; win: boolean }[] = [];
  if (trades?.length && equityCurve.length > 1) {
    const tsStart = equityCurve[0].timestamp;
    const tsEnd   = equityCurve[equityCurve.length - 1].timestamp;
    const span    = tsEnd - tsStart || 1;
    for (const t of trades) {
      const ts = new Date(t.entryDate).getTime();
      if (ts >= tsStart && ts <= tsEnd)
        dots.push({ x: PAD.left + ((ts - tsStart) / span) * INNER_W, win: t.pnl >= 0 });
    }
  }

  return (
    <div className="space-y-2">

      {/* ── Equity Curve ── */}
      <div>
        <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Equity Curve</div>
        <svg viewBox={`0 0 ${W} ${height}`} className="w-full" style={{ height }}>
          {yTicks.map((tick, i) => {
            const y = PAD.top + eqInnerH - ((tick - eqMin) / eqRange) * eqInnerH;
            return (
              <g key={i}>
                <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} stroke="#e5e7eb" strokeWidth="1" />
                <text x={PAD.left - 4} y={y + 4} textAnchor="end" fontSize="10" fill="#9ca3af">
                  {tick >= 1000 ? `${(tick / 1000).toFixed(0)}k` : tick.toFixed(0)}
                </text>
              </g>
            );
          })}
          <path d={fillPath} fill="#3b82f6" opacity="0.1" />
          <path d={eqPath}   fill="none" stroke="#3b82f6" strokeWidth="1.5" />

          {/* Win/loss entry dots */}
          {dots.map((d, i) => (
            <circle key={i} cx={d.x} cy={PAD.top + eqInnerH * 0.5} r="3"
              fill={d.win ? '#16a34a' : '#dc2626'} opacity="0.45" />
          ))}

          {/* Selected-trade lines */}
          {entryX !== null && <>
            <line x1={entryX} x2={entryX} y1={PAD.top} y2={PAD.top + eqInnerH}
              stroke="#16a34a" strokeWidth="1.5" strokeDasharray="4 2" />
            <text x={entryX + 3} y={PAD.top + 11} fontSize="9" fill="#16a34a" fontWeight="600">IN</text>
          </>}
          {exitX !== null && <>
            <line x1={exitX} x2={exitX} y1={PAD.top} y2={PAD.top + eqInnerH}
              stroke="#dc2626" strokeWidth="1.5" strokeDasharray="4 2" />
            <text x={exitX + 3} y={PAD.top + 11} fontSize="9" fill="#dc2626" fontWeight="600">OUT</text>
          </>}
        </svg>
      </div>

      {/* ── Drawdown ── */}
      {hasDd && (
        <div>
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Drawdown</div>
          <svg viewBox={`0 0 ${W} ${DD_H}`} className="w-full" style={{ height: DD_H }}>
            {/* Zero line */}
            <line x1={PAD.left} x2={W - PAD.right} y1={8} y2={8} stroke="#e5e7eb" strokeWidth="1" />
            <text x={PAD.left - 4} y={12} textAnchor="end" fontSize="10" fill="#9ca3af">0%</text>
            {/* Max DD line */}
            <line x1={PAD.left} x2={W - PAD.right} y1={8 + DD_INNER} y2={8 + DD_INNER} stroke="#fecaca" strokeWidth="1" />
            <text x={PAD.left - 4} y={8 + DD_INNER + 4} textAnchor="end" fontSize="10" fill="#f87171">
              {(ddMin * 100).toFixed(1)}%
            </text>
            <path d={ddFill} fill="#ef4444" opacity="0.15" />
            <path d={ddPath} fill="none" stroke="#ef4444" strokeWidth="1.5" />
            {/* Selected-trade lines */}
            {entryX !== null && (
              <line x1={entryX} x2={entryX} y1={8} y2={8 + DD_INNER}
                stroke="#16a34a" strokeWidth="1.5" strokeDasharray="4 2" />
            )}
            {exitX !== null && (
              <line x1={exitX} x2={exitX} y1={8} y2={8 + DD_INNER}
                stroke="#dc2626" strokeWidth="1.5" strokeDasharray="4 2" />
            )}
          </svg>
        </div>
      )}

    </div>
  );
}
