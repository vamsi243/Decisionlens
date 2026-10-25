import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef, type ReactNode } from "react";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const Sheet = Dialog.Root;
export const SheetTrigger = Dialog.Trigger;
export const SheetClose = Dialog.Close;

interface SheetContentProps extends ComponentPropsWithoutRef<typeof Dialog.Content> {
  title: string;
  description?: string;
  side?: "right" | "bottom";
  overlay?: boolean; // false: the page behind stays visible and usable (non-modal panels)
  children: ReactNode;
}

export const SheetContent = forwardRef<ElementRef<typeof Dialog.Content>, SheetContentProps>(
  ({ className, title, description, side = "right", overlay = true, children, ...props }, ref) => (
    <Dialog.Portal>
      {overlay ? <Dialog.Overlay className="sheet-overlay fixed inset-0 z-40 bg-ink/10 backdrop-blur-[2px]" /> : null}
      <Dialog.Content
        ref={ref}
        className={cn(
          "sheet-content fixed z-50 flex flex-col gap-4 border-line bg-surface p-5 shadow-lg focus:outline-none",
          side === "right"
            ? "inset-y-2 right-2 w-[min(440px,calc(100vw-1rem))] rounded-lg border"
            : "inset-x-2 bottom-2 max-h-[85vh] rounded-lg border",
          className,
        )}
        data-side={side}
        {...props}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <Dialog.Title className="font-display text-lg font-extrabold tracking-tight">{title}</Dialog.Title>
            {description ? (
              <Dialog.Description className="mt-0.5 text-sm text-muted">{description}</Dialog.Description>
            ) : (
              <Dialog.Description className="sr-only">{title}</Dialog.Description>
            )}
          </div>
          <Dialog.Close className="rounded-md p-1.5 text-muted hover:bg-panel-2 hover:text-ink" aria-label={useT()("Close")}>
            <X className="size-4" />
          </Dialog.Close>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  ),
);
SheetContent.displayName = "SheetContent";
