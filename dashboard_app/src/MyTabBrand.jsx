export default function MyTabBrand({ onClick, className = '' }) {
  return (
    <button
      type="button"
      className={`mytab-brand ${className}`.trim()}
      onClick={onClick}
      title="Vai alla dashboard"
    >
      <img
        src="/logo.png"
        alt=""
        className="mytab-brand__icon"
        width={40}
        height={40}
        aria-hidden
      />
      <span className="mytab-brand__text">myTab</span>
    </button>
  );
}
