import { useCallback } from "react";

import { api } from "../api";
import { Stat } from "../components/Stat";
import { Status } from "../components/Status";
import { formatDate, formatEur, formatPercent } from "../format";
import { useApi } from "../useApi";

export function Dashboard({ year }: { year: number }) {
  const load = useCallback(() => api.dashboard(year), [year]);
  const { data: overview, error, loading } = useApi(load);

  if (!overview) {
    return <Status loading={loading} error={error} />;
  }

  const savingsShortfall = Number(overview.savings_gap) > 0;

  return (
    <section aria-labelledby="dashboard-title">
      <h2 id="dashboard-title">Overview {overview.year}</h2>
      <div className="stats">
        <Stat label="Freelance gross" value={formatEur(overview.gross)} />
        <Stat
          label={`Savings pool (${formatPercent(overview.savings_pool_rate)})`}
          value={formatEur(overview.savings_target)}
        />
        <Stat
          label="Estimated IRS + Social Security"
          value={formatEur(overview.estimated_obligations)}
          note={`IRS ${formatEur(overview.irs.freelance_tax_impact)} · SS ${formatEur(overview.social_security_total)}`}
        />
        <Stat label="Expected net" value={formatEur(overview.expected_net)} />
      </div>
      {savingsShortfall && (
        <p role="status" className="warning">
          Estimated obligations exceed the savings pool by {formatEur(overview.savings_gap)}.
          Consider raising the savings rate.
        </p>
      )}

      <h3>Monthly</h3>
      <table>
        <thead>
          <tr>
            <th scope="col">Month</th>
            <th scope="col">Gross</th>
            <th scope="col">Set aside</th>
          </tr>
        </thead>
        <tbody>
          {overview.monthly.map((month) => (
            <tr key={month.label}>
              <th scope="row">{month.label}</th>
              <td>{formatEur(month.gross)}</td>
              <td>{formatEur(month.savings_target)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Weekly</h3>
      {overview.weekly.length === 0 ? (
        <p>No payouts recorded for {overview.year}.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">ISO week</th>
              <th scope="col">Gross</th>
              <th scope="col">Set aside</th>
            </tr>
          </thead>
          <tbody>
            {overview.weekly.map((week) => (
              <tr key={week.label}>
                <th scope="row">{week.label}</th>
                <td>{formatEur(week.gross)}</td>
                <td>{formatEur(week.savings_target)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>Social Security by quarter</h3>
      <table>
        <thead>
          <tr>
            <th scope="col">Quarter</th>
            <th scope="col">Services income</th>
            <th scope="col">Monthly contribution</th>
            <th scope="col">Declare by</th>
          </tr>
        </thead>
        <tbody>
          {overview.social_security_quarters.map((quarter) => (
            <tr key={quarter.quarter}>
              <th scope="row">Q{quarter.quarter}</th>
              <td>{formatEur(quarter.services_income)}</td>
              <td>{formatEur(quarter.monthly_contribution)}</td>
              <td>{formatDate(quarter.declaration_deadline)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
