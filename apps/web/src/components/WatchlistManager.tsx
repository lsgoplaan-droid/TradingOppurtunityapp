import { useState } from 'react';
import { WatchlistItem } from '../api/client';

interface Props {
  watchlists: WatchlistItem[];
  onAddWatchlist: (name: string, symbols: string[], market: 'US' | 'INDIA' | 'ALL') => void;
  onSelectWatchlist: (watchlist: WatchlistItem) => void;
}

export function WatchlistManager({ watchlists, onAddWatchlist, onSelectWatchlist }: Props) {
  const [newName, setNewName] = useState('');
  const [newSymbols, setNewSymbols] = useState('');
  const [newMarket, setNewMarket] = useState<'US' | 'INDIA' | 'ALL'>('US');
  const [showForm, setShowForm] = useState(false);

  const handleAdd = () => {
    if (!newName.trim() || !newSymbols.trim()) return;
    const symbols = newSymbols.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    onAddWatchlist(newName.trim(), symbols, newMarket);
    setNewName('');
    setNewSymbols('');
    setShowForm(false);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Watchlists</h3>
        <button
          onClick={() => setShowForm(f => !f)}
          className="text-xs text-blue-600 hover:text-blue-800"
        >
          {showForm ? 'Cancel' : '+ New'}
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-50 rounded-lg p-3 space-y-2">
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="Watchlist name"
            className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <input
            value={newSymbols}
            onChange={e => setNewSymbols(e.target.value)}
            placeholder="AAPL, MSFT, GOOGL"
            className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <div className="flex gap-2">
            <select
              value={newMarket}
              onChange={e => setNewMarket(e.target.value as 'US' | 'INDIA' | 'ALL')}
              className="flex-1 border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
            >
              <option value="US">US</option>
              <option value="INDIA">India</option>
              <option value="ALL">All</option>
            </select>
            <button
              onClick={handleAdd}
              className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
            >
              Add
            </button>
          </div>
        </div>
      )}

      <div className="space-y-1">
        {watchlists.length === 0 && (
          <div className="text-gray-400 text-sm text-center py-4">No watchlists yet</div>
        )}
        {watchlists.map(wl => (
          <button
            key={wl.id}
            onClick={() => onSelectWatchlist(wl)}
            className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-50 border border-transparent text-sm"
          >
            <div className="font-medium text-gray-800">{wl.name}</div>
            <div className="text-xs text-gray-500">
              {wl.symbols.slice(0, 5).join(', ')}{wl.symbols.length > 5 ? ` +${wl.symbols.length - 5}` : ''} &middot; {wl.market}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
