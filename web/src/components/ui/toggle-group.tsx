import * as ToggleGroupPrimitive from "@radix-ui/react-toggle-group";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { cn } from "@/lib/utils";

export const ToggleGroup = forwardRef<
  ElementRef<typeof ToggleGroupPrimitive.Root>,
  ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Root>
>(({ className, ...props }, ref) => (
  <ToggleGroupPrimitive.Root
    ref={ref}
    className={cn(
      "inline-flex items-center gap-0.5 rounded-md border border-line bg-panel-2 p-0.5",
      className,
    )}
    {...props}
  />
));
ToggleGroup.displayName = "ToggleGroup";

export const ToggleGroupItem = forwardRef<
  ElementRef<typeof ToggleGroupPrimitive.Item>,
  ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Item>
>(({ className, ...props }, ref) => (
  <ToggleGroupPrimitive.Item
    ref={ref}
    className={cn(
      "h-7 min-w-8 rounded-[9px] px-2 text-xs font-medium text-muted transition-colors duration-200",
      "hover:text-ink data-[state=on]:bg-surface data-[state=on]:text-ink data-[state=on]:shadow-sm",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30",
      className,
    )}
    {...props}
  />
));
ToggleGroupItem.displayName = "ToggleGroupItem";
