import type { ReactNode } from "react";

type DashboardShellProps = {
  isSidebarOpen: boolean;
  selectedStoreName: string;
  onOpenSidebar: () => void;
  sidebar: ReactNode;
  children: ReactNode;
};

export function DashboardShell({
  isSidebarOpen,
  selectedStoreName,
  onOpenSidebar,
  sidebar,
  children,
}: DashboardShellProps) {
  return (
    <main className={isSidebarOpen ? "dashboard sidebar-open" : "dashboard"}>
      <div className="mobile-shell-bar">
        <button
          type="button"
          className="mobile-menu-button"
          onClick={onOpenSidebar}
          aria-label="Open dashboard menu"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>

        <div className="mobile-shell-title">
          <strong>StorePlug</strong>
          <span>{selectedStoreName}</span>
        </div>
      </div>

      {sidebar}

      <section className="content">{children}</section>
    </main>
  );
}
