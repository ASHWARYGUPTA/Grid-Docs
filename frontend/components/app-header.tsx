import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";

interface AppHeaderProps {
  title: string;
  children?: React.ReactNode;
}

export function AppHeader({ title, children }: AppHeaderProps) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b bg-background/95 backdrop-blur-sm px-4 sticky top-0 z-10">
      <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" />
      <Separator orientation="vertical" className="h-4" />
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage className="font-medium">{title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      {children && (
        <>
          <div className="ml-auto flex items-center gap-2">{children}</div>
        </>
      )}
    </header>
  );
}
