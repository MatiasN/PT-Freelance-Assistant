import { useState } from "react";

import { api } from "./api";
import { Status } from "./components/Status";

import { Calendar } from "./pages/Calendar";
import { Dashboard } from "./pages/Dashboard";
import { Estimator } from "./pages/Estimator";
import { Payouts } from "./pages/Payouts";
import { useApi } from "./useApi";

const TABS = {
  dashboard: "Dashboard",
  payouts: "Payouts & invoices",
  estimator: "Estimator",
  calendar: "Calendar",
} as const;

type Tab = keyof typeof TABS;

function defaultYear(supportedYears: number[]): number | undefined {
  const currentYear = new Date().getFullYear();
  if (supportedYears.includes(currentYear)) {
    return currentYear;
  }
  return supportedYears.at(-1);
}

export function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const { data: supportedYears, error, loading } = useApi(api.fiscalYears);
  const [chosenYear, setChosenYear] = useState<number | null>(null);
  const year = chosenYear ?? (supportedYears ? defaultYear(supportedYears) : undefined);

  return (
    <>
      <header>
        <h1>PT Tax Assistant</h1>
        <label>
          Fiscal year{" "}
          <select
            value={year ?? ""}
            onChange={(event) => setChosenYear(Number(event.target.value))}
          >
            {(supportedYears ?? []).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <nav aria-label="Sections">
          {(Object.keys(TABS) as Tab[]).map((key) => (
            <button
              key={key}
              type="button"
              aria-current={tab === key ? "page" : undefined}
              onClick={() => setTab(key)}
            >
              {TABS[key]}
            </button>
          ))}
        </nav>
      </header>
      <main>
        <Status loading={loading} error={error} />
        {year !== undefined && (
          <>
                {tab === "dashboard" && <Dashboard year={year} />}
            {tab === "payouts" && <Payouts year={year} />}
            {tab === "estimator" && <Estimator year={year} />}
            {tab === "calendar" && <Calendar year={year} />}
          </>
        )}
      </main>
      <footer>
        Organisational and calculation ledger only. PT Tax Assistant never connects to Portal das
        Finanças or Segurança Social Direta and never stores their credentials. Estimates are not
        tax advice — confirm with a certified accountant (contabilista certificado).
      </footer>
    </>
  );
}
