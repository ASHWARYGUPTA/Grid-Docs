"use client";

import { Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface InfoPopoverProps {
  title: string;
  description: string;
  className?: string;
  side?: "top" | "bottom" | "left" | "right";
}

/**
 * InfoPopover — small ⓘ icon that shows a tooltip explaining a section.
 * Drop it next to any section heading or card title.
 *
 * Usage:
 *   <InfoPopover
 *     title="Alert Queue"
 *     description="Live incidents ranked by severity × cascade risk. Click a row to open the dispatch card."
 *   />
 */
export function InfoPopover({
  title,
  description,
  className,
  side = "right",
}: InfoPopoverProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="button"
          tabIndex={0}
          className={cn(
            "inline-flex items-center justify-center size-4 rounded-full",
            "text-muted-foreground/60 hover:text-muted-foreground transition-colors",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-default",
            className
          )}
          aria-label={`About: ${title}`}
        >
          <Info className="size-3.5" />
        </span>
      </TooltipTrigger>
      <TooltipContent
        side={side}
        className="max-w-64 space-y-1 p-3"
        sideOffset={6}
      >
        <p className="text-xs font-semibold">{title}</p>
        <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
      </TooltipContent>
    </Tooltip>
  );
}
