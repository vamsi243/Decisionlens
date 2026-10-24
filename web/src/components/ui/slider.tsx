import * as SliderPrimitive from "@radix-ui/react-slider";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { cn } from "@/lib/utils";

export const Slider = forwardRef<
  ElementRef<typeof SliderPrimitive.Root>,
  ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn("relative flex h-5 w-full touch-none select-none items-center", className)}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-1 w-full grow overflow-hidden rounded-full bg-line-2">
      <SliderPrimitive.Range className="absolute h-full bg-ink" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb
      className="block size-4 rounded-full border-2 border-ink bg-surface shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30"
      aria-label="Position"
    />
  </SliderPrimitive.Root>
));
Slider.displayName = "Slider";
