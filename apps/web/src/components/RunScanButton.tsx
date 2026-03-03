interface Props {
  disabled?: boolean;
  loading?: boolean;
  onClick: () => void;
}

export function RunScanButton({ disabled, loading, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`w-full py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
        disabled || loading
          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
          : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white shadow-sm'
      }`}
    >
      {loading ? (
        <span className="flex items-center justify-center gap-2">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Running Scan...
        </span>
      ) : (
        'Run Scan'
      )}
    </button>
  );
}
