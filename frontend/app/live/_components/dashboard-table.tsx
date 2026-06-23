"use client";

import { Fragment, useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronDown, GripVertical, Plus } from "lucide-react";
import type { QueueItem, ActionCard, PredictedZoneForecast, PropagationMap } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ActionCardPanel } from "./action-card-panel";
import { InfoPopover } from "@/components/info-popover";
import { Calendar } from "lucide-react";
import { api } from "@/lib/api";

interface DashboardTableProps {
  items: QueueItem[];
  selectedEventId: string | null;
  onSelect: (eventId: string | null) => void;
  card: ActionCard | null;
  cardLoading: boolean;
  onMutated: () => void;
  onHoverRoute: (rank: number | null) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onSelectPredicted: (coord: {lat: number; lng: number}) => void;
}

export function DashboardTable({ 
  items, 
  selectedEventId, 
  onSelect,
  card,
  cardLoading,
  onMutated,
  onHoverRoute,
  activeTab,
  setActiveTab,
  onSelectPredicted
}: DashboardTableProps) {
  const [predictedItems, setPredictedItems] = useState<PredictedZoneForecast[]>([]);
  const [cascadeItems, setCascadeItems] = useState<PropagationMap[]>([]);
  const [loadingExtra, setLoadingExtra] = useState(false);

  useEffect(() => {
    const handleTourOpen = () => {
      // If we are already on a card, do nothing
      if (selectedEventId) return;
      // Force switch to active alerts tab and select first row
      if (activeTab !== "outline") setActiveTab("outline");
      if (items.length > 0) {
        onSelect(items[0].event_id);
      }
    };
    window.addEventListener("tour-open-action-card", handleTourOpen);
    return () => window.removeEventListener("tour-open-action-card", handleTourOpen);
  }, [items, selectedEventId, activeTab, onSelect, setActiveTab]);

  const gutterItems = items.filter(i => !i.corridor || i.corridor === "Non-corridor");

  useEffect(() => {
    if (activeTab === "past") {
      setLoadingExtra(true);
      api.hotspotsPredicted(4).then(res => setPredictedItems(res.forecasts)).catch(() => {}).finally(() => setLoadingExtra(false));
    } else if (activeTab === "personnel") {
      setLoadingExtra(true);
      api.propagationActive().then(res => setCascadeItems(res)).catch(() => {}).finally(() => setLoadingExtra(false));
    }
  }, [activeTab]);

  return (
    <div className="flex flex-col h-full bg-card border rounded-lg shadow-sm overflow-hidden">
      {/* Header and Tabs */}
      <div className="flex items-center justify-between p-4 border-b shrink-0">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-auto">
          <TabsList className="h-9 bg-transparent p-0">
            <TabsTrigger
              value="outline"
              className="data-[state=active]:bg-muted data-[state=active]:text-foreground rounded-md px-3 py-1.5 text-xs gap-1.5"
            >
              Observed
              <Badge variant="secondary" className="h-5 px-1.5 rounded-full text-[10px]">{items.length}</Badge>
            </TabsTrigger>
            <TabsTrigger
              value="past"
              className="data-[state=active]:bg-muted data-[state=active]:text-foreground rounded-md px-3 py-1.5 text-xs gap-1.5"
            >
              Predicted
              <Badge variant="secondary" className="h-5 px-1.5 rounded-full text-[10px]">{predictedItems.length}</Badge>
            </TabsTrigger>
            <TabsTrigger
              value="personnel"
              className="data-[state=active]:bg-muted data-[state=active]:text-foreground rounded-md px-3 py-1.5 text-xs gap-1.5"
            >
              Cascade
              <Badge variant="secondary" className="h-5 px-1.5 rounded-full text-[10px]">{cascadeItems.length}</Badge>
            </TabsTrigger>
            <TabsTrigger
              value="gutter"
              className="data-[state=active]:bg-muted data-[state=active]:text-foreground rounded-md px-3 py-1.5 text-xs gap-1.5"
            >
              Gutter Points
              <Badge variant="secondary" className="h-5 px-1.5 rounded-full text-[10px]">{gutterItems.length}</Badge>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader className="bg-muted/30 sticky top-0 z-10 backdrop-blur-sm">
            <TableRow className="border-b">
              <TableHead className="w-12 text-center"></TableHead>
              <TableHead className="w-12 text-center">
                <input type="checkbox" className="rounded border-muted bg-transparent" />
              </TableHead>
              <TableHead className="font-medium text-xs text-muted-foreground w-1/4">
                {activeTab === "past" ? "Corridor" : activeTab === "personnel" ? "Seed Event" : "Event / Location"}
              </TableHead>
              <TableHead className="font-medium text-xs text-muted-foreground">
                {activeTab === "past" ? "Forecast" : activeTab === "personnel" ? "Risk Level" : "Status"}
              </TableHead>
              <TableHead className="font-medium text-xs text-muted-foreground text-right">
                {activeTab === "past" ? "Lift %" : activeTab === "personnel" ? "Seed RCI" : "RCI"}
              </TableHead>
              <TableHead className="font-medium text-xs text-muted-foreground text-right">
                {activeTab === "past" ? "Exp Count" : activeTab === "personnel" ? "Cascade Risk" : "P(Closure)"}
              </TableHead>
              <TableHead className="font-medium text-xs text-muted-foreground">
                {activeTab === "past" ? "System" : activeTab === "personnel" ? "Source" : "Reviewer"}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {activeTab === "outline" && items.map((item) => {
              const isSelected = item.event_id === selectedEventId;
              
              const headerText = item.corridor ?? item.event_id;
              
              const statusColor = item.status === "complete" || item.status === "executed" || item.status === "approved" 
                ? "bg-green-500" 
                : item.status === "rejected" ? "bg-red-500" : "bg-yellow-500";
              const statusLabel = item.status ? (item.status.charAt(0).toUpperCase() + item.status.slice(1)) : "In Process";
              
              const target = (item.rci * 100).toFixed(0);
              const limit = (item.p_closure * 100).toFixed(0);
              const reviewer = item.status === null ? "Assign reviewer" : "System";

              return (
                <Fragment key={item.event_id}>
                  <TableRow
                    onClick={() => onSelect(isSelected ? null : item.event_id)}
                    className={cn(
                      "cursor-pointer hover:bg-muted/50 transition-colors border-b-border/50",
                      isSelected && "bg-muted/80"
                    )}
                  >
                    <TableCell className="text-center">
                      <GripVertical className="size-4 text-muted-foreground/50 inline-block" />
                    </TableCell>
                    <TableCell className="text-center">
                      <input type="checkbox" className="rounded border-muted bg-transparent" onClick={(e) => e.stopPropagation()} />
                    </TableCell>
                    <TableCell className="font-medium text-sm">{headerText}</TableCell>

                    <TableCell>
                      <div className="flex items-center gap-2 border rounded-full px-2 py-0.5 w-fit text-xs text-muted-foreground border-border/60 bg-muted/10">
                        <div className={cn("size-1.5 rounded-full", statusColor)} />
                        {statusLabel}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">{target}</TableCell>
                    <TableCell className="text-right tabular-nums text-sm">{limit}</TableCell>
                    <TableCell>
                      {reviewer === "Assign reviewer" ? (
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          Assign reviewer <ChevronDown className="size-3" />
                        </span>
                      ) : (
                        <span className="text-sm">{reviewer}</span>
                      )}
                    </TableCell>
                  </TableRow>
                  {isSelected && (
                    <TableRow className="bg-muted/5 hover:bg-muted/5 border-b-2 border-b-border">
                      <TableCell colSpan={7} className="p-0">
                        <div id="tour-action-card" className="flex flex-col w-full animate-in slide-in-from-top-2 fade-in duration-200 shadow-inner">
                          <div className="flex items-center justify-between px-6 py-2.5 border-b bg-background/50">
                            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground bg-muted/50 px-2 py-1 rounded-md border border-border/50">
                              <Calendar className="size-3.5" />
                              <span>
                                {card ? new Date(card.created_at).toLocaleString() : "Loading..."}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Action Card</span>
                              <InfoPopover
                                title="Action Card"
                                description="Shows the AI-generated dispatch recommendation for the selected alert. Review the suggested routes, resource allocation, and confidence score before approving or rejecting."
                                side="left"
                              />
                            </div>
                          </div>
                          <div className="p-4 bg-background h-[450px] overflow-hidden rounded-b-md">
                             <ActionCardPanel
                                card={card}
                                loading={cardLoading}
                                onMutated={onMutated}
                                onHoverRoute={onHoverRoute}
                              />
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}

            {activeTab === "gutter" && gutterItems.map((item) => {
              const isSelected = item.event_id === selectedEventId;
              
              const headerText = item.corridor ?? item.event_id;
              
              const statusColor = item.status === "complete" || item.status === "executed" || item.status === "approved" 
                ? "bg-green-500" 
                : item.status === "rejected" ? "bg-red-500" : "bg-yellow-500";
              const statusLabel = item.status ? (item.status.charAt(0).toUpperCase() + item.status.slice(1)) : "In Process";
              
              const target = (item.rci * 100).toFixed(0);
              const limit = (item.p_closure * 100).toFixed(0);
              const reviewer = item.status === null ? "Assign reviewer" : "System";

              return (
                <Fragment key={item.event_id}>
                  <TableRow
                    onClick={() => onSelect(isSelected ? null : item.event_id)}
                    className={cn(
                      "cursor-pointer hover:bg-muted/50 transition-colors border-b-border/50",
                      isSelected && "bg-muted/80"
                    )}
                  >
                    <TableCell className="text-center">
                      <GripVertical className="size-4 text-muted-foreground/50 inline-block" />
                    </TableCell>
                    <TableCell className="text-center">
                      <input type="checkbox" className="rounded border-muted bg-transparent" onClick={(e) => e.stopPropagation()} />
                    </TableCell>
                    <TableCell className="font-medium text-sm">{headerText}</TableCell>

                    <TableCell>
                      <div className="flex items-center gap-2 border rounded-full px-2 py-0.5 w-fit text-xs text-muted-foreground border-border/60 bg-muted/10">
                        <div className={cn("size-1.5 rounded-full", statusColor)} />
                        {statusLabel}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">{target}</TableCell>
                    <TableCell className="text-right tabular-nums text-sm">{limit}</TableCell>
                    <TableCell>
                      {reviewer === "Assign reviewer" ? (
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          Assign reviewer <ChevronDown className="size-3" />
                        </span>
                      ) : (
                        <span className="text-sm">{reviewer}</span>
                      )}
                    </TableCell>
                  </TableRow>
                  {isSelected && (
                    <TableRow className="bg-muted/5 hover:bg-muted/5 border-b-2 border-b-border">
                      <TableCell colSpan={7} className="p-0">
                        <div id="tour-action-card-gutter" className="flex flex-col w-full animate-in slide-in-from-top-2 fade-in duration-200 shadow-inner">
                          <div className="flex items-center justify-between px-6 py-2.5 border-b bg-background/50">
                            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground bg-muted/50 px-2 py-1 rounded-md border border-border/50">
                              <Calendar className="size-3.5" />
                              <span>
                                {card ? new Date(card.created_at).toLocaleString() : "Loading..."}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Action Card</span>
                              <InfoPopover
                                title="Action Card"
                                description="Shows the AI-generated dispatch recommendation for the selected alert. Review the suggested routes, resource allocation, and confidence score before approving or rejecting."
                                side="left"
                              />
                            </div>
                          </div>
                          <div className="p-4 bg-background h-[450px] overflow-hidden rounded-b-md">
                             <ActionCardPanel
                                card={card}
                                loading={cardLoading}
                                onMutated={onMutated}
                                onHoverRoute={onHoverRoute}
                              />
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}

            {activeTab === "past" && predictedItems.map((item, i) => {
              const headerText = item.corridor;
              const target = `+${(item.lift_pct * 100).toFixed(0)}%`;
              const limit = item.expected_count.toString();
              
              return (
                <TableRow 
                  key={`${item.corridor}-${i}`} 
                  className={cn(
                    "border-b-border/50",
                    item.centroid_lat !== null && "cursor-pointer hover:bg-muted/50 transition-colors"
                  )}
                  onClick={() => {
                    if (item.centroid_lat !== null && item.centroid_lon !== null) {
                      onSelectPredicted({ lat: item.centroid_lat, lng: item.centroid_lon });
                    }
                  }}
                >
                  <TableCell className="text-center"><GripVertical className="size-4 text-muted-foreground/50 inline-block" /></TableCell>
                  <TableCell className="text-center"><input type="checkbox" className="rounded border-muted bg-transparent" /></TableCell>
                  <TableCell className="font-medium text-sm">{headerText}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 border rounded-full px-2 py-0.5 w-fit text-xs text-muted-foreground border-border/60 bg-muted/10">
                      <div className="size-1.5 rounded-full bg-blue-500" />
                      Forecast
                    </div>
                  </TableCell>
                  <TableCell className={cn("text-right tabular-nums text-sm", item.lift_pct > 0 && "text-red-500 font-medium")}>{target}</TableCell>
                  <TableCell className="text-right tabular-nums text-sm">{limit}</TableCell>
                  <TableCell><span className="text-sm">System</span></TableCell>
                </TableRow>
              );
            })}

            {activeTab === "personnel" && cascadeItems.map((item) => {
              const headerText = items.find(i => i.event_id === item.event_id)?.corridor || item.event_id;
              const target = (item.seed_rci * 100).toFixed(0);
              const limit = (item.cascade_risk * 100).toFixed(0);
              
              return (
                <TableRow 
                  key={item.event_id} 
                  className="cursor-pointer hover:bg-muted/50 transition-colors border-b-border/50"
                  onClick={() => onSelect(item.event_id)}
                >
                  <TableCell className="text-center"><GripVertical className="size-4 text-muted-foreground/50 inline-block" /></TableCell>
                  <TableCell className="text-center"><input type="checkbox" className="rounded border-muted bg-transparent" /></TableCell>
                  <TableCell className="font-medium text-sm">{headerText}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 border rounded-full px-2 py-0.5 w-fit text-xs text-muted-foreground border-border/60 bg-muted/10">
                      <div className="size-1.5 rounded-full bg-red-500" />
                      High Risk
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm text-red-500 font-medium">{target}</TableCell>
                  <TableCell className="text-right tabular-nums text-sm">{limit}</TableCell>
                  <TableCell><span className="text-sm">System</span></TableCell>
                </TableRow>
              );
            })}

            {loadingExtra && (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground text-sm">
                  Loading data...
                </TableCell>
              </TableRow>
            )}

            {activeTab === "outline" && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground text-sm">
                  No active events
                </TableCell>
              </TableRow>
            )}
            {activeTab === "gutter" && gutterItems.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground text-sm">
                  No gutter points
                </TableCell>
              </TableRow>
            )}
            {activeTab === "past" && !loadingExtra && predictedItems.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground text-sm">
                  No predicted forecasts
                </TableCell>
              </TableRow>
            )}
            {activeTab === "personnel" && !loadingExtra && cascadeItems.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground text-sm">
                  No active cascade risks
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
