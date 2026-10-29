export function Status({ loading, error }: { loading: boolean; error: string | null }) {
  if (error) {
    return (
      <p role="alert" className="error">
        {error}
      </p>
    );
  }
  if (loading) {
    return <p aria-live="polite">Loading…</p>;
  }
  return null;
}
