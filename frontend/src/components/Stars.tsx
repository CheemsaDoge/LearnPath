import { Star } from "lucide-react";

export function Stars({ value, size = 14, className = "" }: { value: number; size?: number; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-0.5 ${className}`} aria-label={`${value} 星`}>
      {[1, 2, 3].map((i) => (
        <Star key={i} size={size} className={i <= value ? "fill-amber-400 text-amber-400" : "text-slate-300"} strokeWidth={1.75} />
      ))}
    </span>
  );
}
