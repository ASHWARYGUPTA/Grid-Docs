import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ElementType;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  className?: string;
  valueClassName?: string;
}

export function StatCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
  trendValue,
  className,
  valueClassName,
}: StatCardProps) {
  const TrendIcon =
    trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor =
    trend === "up"
      ? "text-live border-live/30 bg-live/10"
      : trend === "down"
        ? "text-destructive border-destructive/30 bg-destructive/10"
        : "text-muted-foreground border-border bg-muted/40";

  return (
    <Card
      className={cn(
        "transition-shadow duration-200 hover:shadow-md",
        className
      )}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardDescription className="text-sm font-medium">{title}</CardDescription>
        {Icon && <Icon className="size-4 text-muted-foreground" />}
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            "text-2xl font-bold tabular-nums tracking-tight",
            valueClassName
          )}
        >
          {value}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
        {trendValue && (
          <Badge
            variant="outline"
            className={cn("mt-2 gap-1 text-xs", trendColor)}
          >
            <TrendIcon className="size-3" />
            {trendValue}
          </Badge>
        )}
      </CardContent>
    </Card>
  );
}
