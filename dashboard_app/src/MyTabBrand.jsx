import { Cigarette } from 'lucide-react';

export default function MyTabBrand({ onClick, className = '' }) {
  return (
    <button
      type="button"
      className={`mytab-brand ${className}`.trim()}
      onClick={onClick}
      title="Vai alla dashboard"
    >
      <Cigarette size={28} color="var(--accent)" aria-hidden />
      <span>myTab</span>
    </button>
  );
}
