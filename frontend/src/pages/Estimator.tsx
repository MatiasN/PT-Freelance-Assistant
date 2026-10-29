import { type FormEvent, useState } from "react";

import { type IrsEstimate, type QuarterlySocialSecurity, api } from "../api";
import { Stat } from "../components/Stat";
import { formatDate, formatEur, formatPercent } from "../format";

function IrsEstimator({ year }: { year: number }) {
  const [freelanceGross, setFreelanceGross] = useState("20000");
  const [employmentGross, setEmploymentGross] = useState("42000");
  const [estimate, setEstimate] = useState<IrsEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      setEstimate(await api.irsEstimate(year, freelanceGross, employmentGross));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not estimate IRS");
    }
  }

  return (
    <section aria-labelledby="irs-title" className="panel">
      <h3 id="irs-title">IRS — Regime Simplificado (Anexo B) + employment (Anexo A)</h3>
      <form onSubmit={submit} className="inline-form">
        <label>
          Annual freelance gross (€)
          <input
            type="number"
            min="0"
            step="0.01"
            required
            value={freelanceGross}
            onChange={(event) => setFreelanceGross(event.target.value)}
          />
        </label>
        <label>
          Annual employment gross (€)
          <input
            type="number"
            min="0"
            step="0.01"
            required
            value={employmentGross}
            onChange={(event) => setEmploymentGross(event.target.value)}
          />
        </label>
        <button type="submit">Estimate</button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {estimate && (
        <>
          <div className="stats">
            <Stat
              label={`Taxable freelance base (${formatPercent(estimate.simplified_regime_coefficient)})`}
              value={formatEur(estimate.freelance_taxable_income)}
            />
            <Stat
              label="Extra IRS caused by freelance income"
              value={formatEur(estimate.freelance_tax_impact)}
              note={`${formatPercent(estimate.freelance_effective_rate)} of freelance gross`}
            />
            <Stat
              label="Marginal rate"
              value={formatPercent(estimate.tax_with_freelance.marginal_rate)}
              note={`was ${formatPercent(estimate.tax_without_freelance.marginal_rate)} on salary alone`}
            />
          </div>
          <table>
            <caption>Brackets applied to combined taxable income</caption>
            <thead>
              <tr>
                <th scope="col">Bracket</th>
                <th scope="col">Rate</th>
                <th scope="col">Income in bracket</th>
                <th scope="col">Tax</th>
              </tr>
            </thead>
            <tbody>
              {estimate.tax_with_freelance.slices.map((slice) => (
                <tr key={slice.lower_limit}>
                  <th scope="row">
                    {formatEur(slice.lower_limit)} –{" "}
                    {slice.upper_limit ? formatEur(slice.upper_limit) : "∞"}
                  </th>
                  <td>{formatPercent(slice.rate)}</td>
                  <td>{formatEur(slice.taxable_in_bracket)}</td>
                  <td>{formatEur(slice.tax)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note">
            Before deduções à coleta and salary withholding. Mainland rates only.
          </p>
        </>
      )}
    </section>
  );
}

function SocialSecurityEstimator({ year }: { year: number }) {
  const [quarter, setQuarter] = useState(1);
  const [servicesIncome, setServicesIncome] = useState("15000");
  const [estimate, setEstimate] = useState<QuarterlySocialSecurity | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      setEstimate(await api.socialSecurityEstimate(year, quarter, servicesIncome));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not estimate contributions");
    }
  }

  return (
    <section aria-labelledby="ss-title" className="panel">
      <h3 id="ss-title">Segurança Social — quarterly declaration</h3>
      <form onSubmit={submit} className="inline-form">
        <label>
          Quarter
          <select value={quarter} onChange={(event) => setQuarter(Number(event.target.value))}>
            {[1, 2, 3, 4].map((option) => (
              <option key={option} value={option}>
                Q{option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Services income in quarter (€)
          <input
            type="number"
            min="0"
            step="0.01"
            required
            value={servicesIncome}
            onChange={(event) => setServicesIncome(event.target.value)}
          />
        </label>
        <button type="submit">Estimate</button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {estimate && (
        <div className="stats">
          <Stat
            label="Relevant income (70%) / month"
            value={formatEur(estimate.monthly_average_relevant_income)}
          />
          <Stat label="Exempt up to (4 × IAS)" value={formatEur(estimate.exempt_threshold)} />
          <Stat
            label="Monthly contribution (21.4%)"
            value={formatEur(estimate.monthly_contribution)}
            note={`${formatEur(estimate.quarterly_contribution)} over 3 months`}
          />
          <Stat label="Declare by" value={formatDate(estimate.declaration_deadline)} />
        </div>
      )}
    </section>
  );
}

export function Estimator({ year }: { year: number }) {
  return (
    <section aria-labelledby="estimator-title">
      <h2 id="estimator-title">Tax & Social Security estimator {year}</h2>
      <IrsEstimator year={year} />
      <SocialSecurityEstimator year={year} />
    </section>
  );
}
