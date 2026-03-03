import { ScanTemplate } from '../api/client';

interface Props {
  templates: ScanTemplate[];  // pre-filtered by parent to current market + assetClass
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading?: boolean;
}

export function ScanTemplateSelector({ templates, selectedId, onSelect, loading }: Props) {
  if (loading) {
    return <div className="text-gray-400 text-sm py-2">Loading templates...</div>;
  }

  if (templates.length === 0) {
    return <div className="text-gray-400 text-sm py-2">No templates for this selection.</div>;
  }

  const standard = templates.filter(t => t.type !== 'mtf');
  const mtf = templates.filter(t => t.type === 'mtf');

  const renderTemplate = (t: ScanTemplate) => {
    const isIndia = t.market === 'INDIA';
    const isMTF = t.type === 'mtf';
    const selected = selectedId === t.id;
    return (
      <button
        key={t.id}
        onClick={() => onSelect(t.id)}
        className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors border ${
          selected
            ? isMTF
              ? 'bg-indigo-50 border-indigo-300 text-indigo-800'
              : isIndia
              ? 'bg-orange-50 border-orange-200 text-orange-800'
              : 'bg-blue-50 border-blue-200 text-blue-800'
            : 'border-transparent hover:bg-gray-50 text-gray-700'
        }`}
      >
        <div className="flex items-center gap-1.5">
          <span className="font-medium">{t.name}</span>
          {isMTF && (
            <span className="bg-indigo-100 text-indigo-600 text-xs px-1.5 py-0.5 rounded font-semibold leading-none">
              MTF
            </span>
          )}
        </div>
        <div className="text-xs text-gray-500 mt-0.5">{t.description}</div>
        {isMTF && t.timeframes ? (
          <div className="flex gap-1 mt-0.5 flex-wrap">
            {t.timeframes.map(tf => (
              <span key={tf} className="text-xs bg-indigo-50 text-indigo-500 px-1 rounded">{tf}</span>
            ))}
          </div>
        ) : (
          <div className="text-xs text-gray-400 mt-0.5">{t.timeframe}</div>
        )}
      </button>
    );
  };

  return (
    <div className="space-y-1">
      {standard.map(renderTemplate)}
      {mtf.length > 0 && (
        <>
          <div className="text-xs font-semibold text-indigo-600 uppercase tracking-wide pt-2 pb-0.5 px-1">
            Multi-Timeframe
          </div>
          {mtf.map(renderTemplate)}
        </>
      )}
    </div>
  );
}
