import { CopticCross } from "./coptic-cross";

export function CrossDivider({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center gap-4 my-8 ${className}`}>
      <span className="h-px flex-1 bg-gradient-to-l from-gold-800 via-gold to-transparent" />
      <CopticCross size={28} className="text-gold-200" />
      <span className="h-px flex-1 bg-gradient-to-r from-gold-800 via-gold to-transparent" />
    </div>
  );
}

export function CornerOrnament({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      className={className}
      aria-hidden
      xmlns="http://www.w3.org/2000/svg"
    >
      <g stroke="currentColor" strokeWidth="1" fill="none">
        <path d="M0 0 L40 0 L40 40" />
        <path d="M4 4 L36 4 L36 36" opacity="0.6" />
        <path d="M8 8 L20 8 M8 8 L8 20" opacity="0.8" />
        <circle cx="32" cy="8" r="2" fill="currentColor" stroke="none" opacity="0.7" />
        <circle cx="8" cy="32" r="2" fill="currentColor" stroke="none" opacity="0.7" />
      </g>
    </svg>
  );
}
