export default function Card({ children, className = "", noPadding = false }) {
  return (
    <div className={`app-card overflow-hidden ${noPadding ? "" : "p-4"} ${className}`}>
      {children}
    </div>
  );
}
