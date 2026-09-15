/**
 * Die Wortmarke braucht ein Zeichen, das auch bei 20 px trägt. Zwei Segel am
 * Mast: das Vorsegel gefüllt, das Groß als Umriss, darunter die Wasserlinie.
 * Bewusst kein Anker – der steht für Stillstand, nicht für Segeln.
 */
export default function Burgee({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={className} fill="none">
      <path d="M11.2 3.2 4.6 15.2h6.6V3.2Z" fill="currentColor" opacity="0.92" />
      <path
        d="M12.9 6.1v9.1h6.1c0-3.6-2.2-7-6.1-9.1Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M2.8 18.2h18.4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.55"
      />
    </svg>
  );
}
