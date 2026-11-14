import mandarinoImg from "../../assets/mandarino-avatar.png";

interface MandarinoAvatarProps {
  size?: "xs" | "sm" | "md" | "xl";
  pensando?: boolean;
  flotar?: boolean;
  className?: string;
}

const SIZE_CLASSES: Record<NonNullable<MandarinoAvatarProps["size"]>, string> = {
  xs: "h-7 w-7",
  sm: "h-9 w-9",
  md: "h-11 w-11",
  xl: "h-28 w-28 sm:h-32 sm:w-32",
};

export function MandarinoAvatar({
  size = "sm",
  pensando = false,
  flotar = false,
  className = "",
}: MandarinoAvatarProps) {
  const dim = SIZE_CLASSES[size];

  return (
    <div
      className={`relative inline-flex shrink-0 items-center justify-center ${dim} ${className}`}
      aria-hidden="true"
    >
      {/* Halo naranja cálido sin fondo azul */}
      <span
        className={`pointer-events-none absolute inset-0 rounded-full ${
          size === "xl"
            ? "bg-[radial-gradient(circle,rgba(249,115,22,0.28)_0%,rgba(249,115,22,0.06)_55%,transparent_75%)]"
            : "bg-[radial-gradient(circle,rgba(249,115,22,0.22)_0%,transparent_72%)]"
        }`}
      />
      {(pensando || size === "xl") && (
        <span
          className={`mandarino-ring pointer-events-none absolute inset-0 rounded-full border border-dashed ${
            pensando ? "border-[#f97316]" : "border-[#fb923c]/50"
          }`}
        />
      )}
      <img
        src={mandarinoImg}
        alt=""
        className={`relative h-[88%] w-[88%] select-none object-contain ${
          flotar || size === "xl" ? "mandarino-sway" : ""
        }`}
      />
    </div>
  );
}
