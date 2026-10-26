export function EvidenceChip({
  id,
  onSelect,
}: {
  id: string;
  onSelect?: (id: string) => void;
}) {
  if (!onSelect) {
    return <code className="chip">{id}</code>;
  }
  return (
    <button type="button" className="chip chip-button" onClick={() => onSelect(id)}>
      {id}
    </button>
  );
}
