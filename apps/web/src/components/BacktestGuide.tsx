import { useState } from 'react';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-gray-100 last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between py-2.5 text-left text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
      >
        {title}
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="pb-3 text-sm text-gray-600 leading-relaxed space-y-2">{children}</div>}
    </div>
  );
}

function Term({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="font-semibold text-gray-700 shrink-0 w-32">{label}</span>
      <span>{children}</span>
    </div>
  );
}

export function BacktestGuide() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-blue-500 text-lg">?</span>
          <span className="text-sm font-semibold text-gray-700">
            How Backtesting Works — A Guide for Investors
          </span>
        </div>
        <span className="text-xs text-gray-400">{expanded ? 'Hide' : 'Show'}</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100">
          {/* ── What is backtesting ───────────────────────────── */}
          <Section title="What is backtesting?">
            <p>
              Backtesting answers: <strong>"If I had followed this trading strategy in the past,
              how much money would I have made or lost?"</strong>
            </p>
            <p>
              The app takes historical stock prices, applies the entry and exit rules of a strategy,
              and simulates every trade as if you had made it in real time. It then calculates
              performance metrics so you can decide whether a strategy is worth using with real money.
            </p>
            <p className="text-amber-700 bg-amber-50 px-2.5 py-1.5 rounded text-xs">
              Past performance does not guarantee future results. Backtesting shows what
              <em> would have </em> happened, not what <em>will</em> happen. Always paper-trade a
              strategy before risking real capital.
            </p>
          </Section>

          {/* ── Form fields ──────────────────────────────────── */}
          <Section title="Setting up a backtest (form fields)">
            <Term label="Symbol">
              The stock ticker you want to test (e.g. AAPL for Apple, RELIANCE.NS for Reliance on NSE).
            </Term>
            <Term label="Strategy">
              The set of rules that decide when to buy and sell. Each strategy uses different technical
              indicators — see the "Strategies" section below.
            </Term>
            <Term label="Start / End Date">
              The historical period to test. Use at least 2–3 years to get meaningful results.
              Short periods can be misleading because a strategy might get lucky or unlucky.
            </Term>
            <Term label="Initial Capital">
              How much money you're starting with (in dollars). This affects the size of each position
              and the dollar amounts shown in results.
            </Term>
            <Term label="Position Sizing">
              How much of your capital goes into each trade:
              <ul className="list-disc ml-4 mt-1 space-y-0.5 text-xs">
                <li><strong>% of Equity (10%)</strong> — Each trade uses 10% of your current balance. As you win, trades get bigger; as you lose, they get smaller. This is the safest default.</li>
                <li><strong>Fixed ($10k)</strong> — Every trade uses $10,000 regardless of your balance.</li>
                <li><strong>Half-Kelly</strong> — A math-based formula that sizes trades based on your win rate and average win/loss. It maximizes growth but can be aggressive — "half" Kelly is the conservative version.</li>
              </ul>
            </Term>
            <Term label="Commission">
              The percentage fee your broker charges per trade (0.1% = $1 per $1,000 traded).
              Commission is applied on both the buy and the sell. Most online brokers charge between
              0% and 0.1%.
            </Term>

            <div className="mt-2 pt-2 border-t border-gray-100">
              <p className="font-semibold text-gray-700 mb-1">Options-only fields</p>
              <Term label="Expiry (days)">
                How many days until the option expires. 30 days is standard for monthly options.
                Shorter expiry (7–14 days) means more time decay but higher risk.
              </Term>
              <Term label="Strike offset %">
                How far from the current stock price to place the strike.
                0% = at-the-money (ATM). 5% = 5% out-of-the-money (OTM). OTM options are cheaper
                but need a bigger price move to profit.
              </Term>
              <Term label="Wing width %">
                (Iron Condor only) The distance between the short and long strikes.
                Wider wings = higher max loss but also more credit received.
              </Term>
            </div>
          </Section>

          {/* ── Strategies ───────────────────────────────────── */}
          <Section title="Available strategies explained">
            <p className="font-semibold text-gray-700 mb-1">Equity (stock) strategies</p>
            <Term label="Golden Cross">
              Buys when the 50-day moving average crosses above the 200-day moving average.
              This is a classic trend-following signal — it means the stock's short-term momentum
              is turning positive relative to the long-term trend.
            </Term>
            <Term label="RSI Mean Reversion">
              Buys when the RSI indicator drops below 30 (oversold) and then bounces back above 30.
              The idea: stocks that fall too fast tend to snap back.
              Best for range-bound or blue-chip stocks, not strong downtrends.
            </Term>
            <Term label="MACD Trend">
              Buys when the MACD line crosses above its signal line.
              MACD measures the difference between fast and slow moving averages — when it crosses
              up, momentum is accelerating.
            </Term>
            <Term label="Bollinger Reversion">
              Buys when price touches the lower Bollinger Band and closes back inside.
              Bollinger Bands measure how far price has strayed from average — touching the lower
              band suggests the stock is stretched to the downside.
            </Term>

            <p className="font-semibold text-gray-700 mt-3 mb-1">Options strategies</p>
            <Term label="Long Call">
              Buy a call option — you profit if the stock goes up. Your max loss is limited to the
              premium you paid.
            </Term>
            <Term label="Long Put">
              Buy a put option — you profit if the stock goes down. Max loss = premium paid.
              This is like buying insurance against a drop.
            </Term>
            <Term label="Straddle">
              Buy both a call and a put at the same strike. You profit if the stock makes a big move
              in either direction. You lose if it stays flat (because both options lose value from
              time decay).
            </Term>
            <Term label="Iron Condor">
              Sell an OTM call spread and an OTM put spread. You collect premium upfront and profit
              if the stock stays within a price range. Max profit = credit received. Max loss = wing
              width minus credit. Best when you expect low volatility.
            </Term>
            <Term label="Covered Call">
              Own 100 shares and sell a call against them. You collect monthly premium income but
              give up upside above the strike price. This is a conservative income strategy.
            </Term>
          </Section>

          {/* ── Result metrics ───────────────────────────────── */}
          <Section title="Understanding the result metrics">
            <p className="font-semibold text-gray-700 mb-1">Performance numbers</p>
            <Term label="Total Return">
              Your overall profit or loss as a percentage. +25% means you turned $100,000 into $125,000.
            </Term>
            <Term label="CAGR">
              Compound Annual Growth Rate — your return smoothed out to a yearly rate. This lets
              you compare strategies across different time periods. A CAGR above 10–15% is strong
              for most strategies.
            </Term>
            <Term label="Sharpe Ratio">
              Measures return per unit of risk. Higher is better. Below 0.5 = poor, 0.5–1.0 = okay,
              above 1.0 = good, above 2.0 = excellent. It penalizes strategies that are
              volatile even if they make money.
            </Term>
            <Term label="Sortino Ratio">
              Like Sharpe but only penalizes downside volatility (drops). A strategy that
              has big upside swings but small downside will have a better Sortino than Sharpe.
              Above 1.0 is good.
            </Term>
            <Term label="Max Drawdown">
              The biggest peak-to-trough drop during the test period. If your account went from
              $120,000 to $90,000, that's a 25% drawdown. This tells you the worst pain you would
              have experienced. Keep in mind: in live trading, your actual drawdown could be worse.
            </Term>

            <p className="font-semibold text-gray-700 mt-3 mb-1">Trade statistics</p>
            <Term label="Win Rate">
              The percentage of trades that made money. 50–60% is typical for trend-following
              strategies. Some strategies work with only 30–40% wins but make it up with large
              winners.
            </Term>
            <Term label="Profit Factor">
              Total dollars won divided by total dollars lost. Above 1.0 = profitable.
              1.5 or higher is good. 2.0+ is excellent. Below 1.0 means the strategy lost money.
            </Term>
            <Term label="Trades">
              How many trades occurred. More trades = more statistical confidence.
              Fewer than 10 trades makes results unreliable — extend your date range.
            </Term>

            <p className="font-semibold text-gray-700 mt-3 mb-1">Options-specific metrics</p>
            <Term label="Expired Worthless">
              Percentage of options trades where the option lost all value by expiry.
              High numbers mean the strategy is buying options that expire before moving enough.
              For selling strategies (iron condor), high expiry = good (you keep the premium).
            </Term>
            <Term label="Avg DTE at Exit">
              Average days-to-expiration when you closed the trade. Exiting earlier preserves
              time value; exiting near expiry means you're exposed to rapid time decay.
            </Term>
          </Section>

          {/* ── Charts ───────────────────────────────────────── */}
          <Section title="Reading the charts">
            <Term label="Equity Curve">
              The blue line shows your account balance over time. An upward-sloping line means
              the strategy is making money. Flat or downward = losing periods. Green/red dots
              mark individual trade entries.
            </Term>
            <Term label="Drawdown Chart">
              The red area below the equity curve shows how far your account is below its
              previous high at any given time. Shallow, brief dips are normal. Deep, prolonged
              dips mean the strategy went through a rough stretch.
            </Term>
            <Term label="Click a trade">
              Click any row in the trades table to highlight that trade's entry (green dashed line)
              and exit (red dashed line) on both charts. This helps you understand what the market
              was doing when each trade happened.
            </Term>
          </Section>

          {/* ── Trading plan ─────────────────────────────────── */}
          <Section title="Understanding the Trading Plan">
            <Term label="Edge rating">
              Combines win rate and profit factor into a simple rating. "Strong edge" means
              the strategy has a clear statistical advantage. "Weak edge" means results are marginal
              — you should paper-trade before using real money.
            </Term>
            <Term label="Risk per trade">
              The suggested percentage of your total capital to put into each trade, calculated
              using the half-Kelly formula. This balances growth against the risk of large losses.
              1–2% per trade is typical for conservative investors.
            </Term>
            <Term label="Initial stop">
              A suggested price level where you should exit a losing trade to limit damage.
              Based on 60% of the strategy's historical max drawdown.
            </Term>
            <Term label="Avg hold time">
              How long trades typically last. Short hold times (1–5 bars) suit active traders.
              Longer holds (20+ bars) suit swing or position traders.
            </Term>
            <Term label="Profit target">
              A suggested level to take profits, expressed as a multiple of your initial risk.
              For example, "2.0x" means if you risked $1, target $2 of profit.
            </Term>
          </Section>

          {/* ── Tips ─────────────────────────────────────────── */}
          <Section title="Tips for beginners">
            <ul className="list-disc ml-4 space-y-1.5">
              <li>
                <strong>Test multiple strategies</strong> on the same stock. If only one strategy
                works, the result might be a fluke. If several agree, there's real opportunity.
              </li>
              <li>
                <strong>Use at least 2–3 years of data.</strong> A strategy that only works in
                a bull market will fail when the market turns.
              </li>
              <li>
                <strong>Watch the drawdown, not just the return.</strong> A strategy that makes
                50% but drops 40% along the way is very hard to stick with emotionally.
              </li>
              <li>
                <strong>Start with "% of Equity" sizing.</strong> It's the safest default —
                you automatically risk less when losing and more when winning.
              </li>
              <li>
                <strong>Paper-trade first.</strong> Run the strategy in a demo account for 1–2
                months before committing real money.
              </li>
              <li>
                <strong>Commission matters.</strong> If you trade frequently, even small commissions
                add up. Make sure your profit factor stays above 1.0 after costs.
              </li>
              <li>
                <strong>Past results ≠ future results.</strong> The market changes. A backtest
                tells you what <em>did</em> happen, not what <em>will</em> happen. Use it as one
                input, not the only input.
              </li>
            </ul>
          </Section>
        </div>
      )}
    </div>
  );
}
