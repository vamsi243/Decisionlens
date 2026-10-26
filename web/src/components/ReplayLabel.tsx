import { LoaderCircle, RotateCcw } from "lucide-react";
import { useReplay } from "@/lib/clip";
import { useT } from "@/lib/i18n";

/** The inside of a Replay button: a spinner while the clip loads, a note if it couldn't. */
export function ReplayLabel({ id, label }: { id: string; label: string }) {
  const t = useT();
  const state = useReplay((r) => (r.id === id ? r.state : null));
  if (state === "loading")
    return (
      <>
        <LoaderCircle className="size-3.5 animate-spin" aria-hidden /> {t("Loading…")}
      </>
    );
  if (state === "failed")
    return (
      <span role="status" title={t("The replay couldn't load. Try again.")} className="inline-flex items-center gap-1 text-red">
        <RotateCcw className="size-3.5" aria-hidden /> {t("Try again")}
      </span>
    );
  return (
    <>
      <RotateCcw className="size-3.5" aria-hidden /> {t(label)}
    </>
  );
}
