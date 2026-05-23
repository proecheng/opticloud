import type { IPAttribution } from "@/lib/api";

const ATTRIBUTION_STYLE: Record<IPAttribution["tier"], string> = {
  L1: "border-primary/40 bg-primary/10 text-primary",
  L2: "border-success/40 bg-success/10 text-success",
  L3: "border-border bg-muted text-muted-foreground",
};

export function AttributionBadge({
  attribution,
  className = "",
}: {
  attribution: IPAttribution;
  className?: string;
}): JSX.Element {
  return (
    <span
      data-testid={`attribution-badge-${attribution.tier}`}
      title={attribution.label_zh}
      className={
        "inline-flex h-6 min-w-10 items-center justify-center rounded-md border px-2 " +
        "font-mono text-xs font-semibold leading-none " +
        ATTRIBUTION_STYLE[attribution.tier] +
        (className ? ` ${className}` : "")
      }
    >
      {attribution.tier}
    </span>
  );
}

export function attributionLine(attribution: IPAttribution): string {
  if (attribution.visibility === "full_visible") {
    return `Algorithm by ${attribution.display_name_zh}`;
  }
  return attribution.summary_zh;
}
