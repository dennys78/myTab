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
        alt="myTab"
        className="mytab-brand__logo"
        width={140}
        height={78}
      />
    </button>
  );
}
