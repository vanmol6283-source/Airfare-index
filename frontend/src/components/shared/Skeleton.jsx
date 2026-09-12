export default function Skeleton({ className = "", width, height, circle = false }) {
  const style = {
    width: width || "100%",
    height: height || "1em",
    borderRadius: circle ? "50%" : "0.5rem"
  };
  return (
    <div
      className={`animate-skeleton ${className}`}
      style={style}
      aria-hidden="true"
    />
  );
}
