type Market = 'US' | 'INDIA';
type AssetClass = 'EQUITY' | 'EQUITY_OPTIONS';

interface Props {
  market: Market;
  assetClass: AssetClass;
  onMarketChange: (m: Market) => void;
  onAssetClassChange: (a: AssetClass) => void;
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex bg-gray-100 rounded-lg p-0.5 gap-0.5">
      {options.map(opt => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`flex-1 py-1 text-xs font-medium rounded-md transition-colors ${
            value === opt.value
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function MarketAssetSelector({ market, assetClass, onMarketChange, onAssetClassChange }: Props) {
  return (
    <div className="space-y-2">
      <SegmentedControl
        options={[
          { value: 'US', label: 'US' },
          { value: 'INDIA', label: 'India' },
        ]}
        value={market}
        onChange={onMarketChange}
      />
      <SegmentedControl
        options={[
          { value: 'EQUITY', label: 'Equity' },
          { value: 'EQUITY_OPTIONS', label: 'Options' },
        ]}
        value={assetClass}
        onChange={onAssetClassChange}
      />
    </div>
  );
}
