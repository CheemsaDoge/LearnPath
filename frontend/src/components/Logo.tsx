import { Link } from "react-router-dom";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link to="/" className={`inline-flex items-center gap-2 ${className}`}>
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500 text-white">
        <svg viewBox="0 0 64 64" className="h-5 w-5" fill="none">
          <circle cx="20" cy="44" r="6" fill="currentColor" />
          <circle cx="32" cy="24" r="6" fill="currentColor" />
          <circle cx="46" cy="40" r="6" fill="currentColor" />
          <path d="M20 44 L32 24 L46 40" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="text-[17px] font-bold tracking-tight">
        知径 <span className="text-brand-500">LearnWay</span>
      </span>
    </Link>
  );
}
