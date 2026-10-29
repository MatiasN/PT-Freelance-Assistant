import { useCallback, useState } from "react";

import { type SyncReport, api } from "../api";
import { Status } from "../components/Status";
import { formatDate } from "../format";
import { useApi } from "../useApi";

export function Calendar({ year }: { year: number }) {
  const loadDeadlines = useCallback(() => api.deadlines(year), [year]);
  const { data: deadlines, error, loading } = useApi(loadDeadlines);
  const { data: status } = useApi(api.calendarStatus);
  const [syncing, setSyncing] = useState(false);
  const [report, setReport] = useState<SyncReport | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  async function sync() {
    setSyncing(true);
    setSyncError(null);
    try {
      setReport(await api.syncCalendar(year));
    } catch (caught) {
      setSyncError(caught instanceof Error ? caught.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <section aria-labelledby="calendar-title">
      <h2 id="calendar-title">Fiscal deadlines {year}</h2>
      <div className="panel">
        <p>
          {status?.configured
            ? `Nextcloud calendar: ${status.calendar_url}`
            : "Nextcloud CalDAV is not configured. Set the PTTAX_CALDAV_* variables."}
        </p>
        <button type="button" onClick={sync} disabled={syncing || !status?.configured}>
          {syncing ? "Pushing…" : "Push deadlines to Nextcloud"}
        </button>{" "}
        <a href={`/api/calendar/deadlines.ics?year=${year}`} download>
          Download .ics
        </a>
        {report && (
          <p role="status">
            Pushed {report.pushed} events.
            {report.failed.length > 0 && ` ${report.failed.length} failed: ${report.failed.join("; ")}`}
          </p>
        )}
        {syncError && (
          <p role="alert" className="error">
            {syncError}
          </p>
        )}
      </div>

      <Status loading={loading} error={error} />
      {deadlines && (
        <ul className="deadlines">
          {deadlines.map((deadline) => (
            <li key={deadline.key}>
              <details>
                <summary>
                  <time dateTime={deadline.due}>{formatDate(deadline.due)}</time> —{" "}
                  {deadline.title}
                  {deadline.repeat_every_days && ` (every ${deadline.repeat_every_days} days)`}
                </summary>
                <pre>{deadline.guide_markdown.trim()}</pre>
                <ul>
                  {deadline.links.map((link) => (
                    <li key={link.url}>
                      <a href={link.url} target="_blank" rel="noreferrer noopener">
                        {link.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
