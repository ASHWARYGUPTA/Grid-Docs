import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: React.ElementType;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center gap-3 animate-in fade-in-0 duration-300",
        className
      )}
    >
      <div className="rounded-full bg-muted p-4 ring-1 ring-border">
        <Icon className="size-7 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <h3 className="font-medium text-sm text-foreground">{title}</h3>
        {description && (
          <p className="text-sm text-muted-foreground max-w-xs">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
