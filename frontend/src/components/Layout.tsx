import { useState, type ReactNode } from "react";
import type { Page, User } from "../types";
import { titleCase } from "../utils";
import { Icon, type IconName } from "./Icon";

interface NavItem {
  page: Page;
  label: string;
  icon: IconName;
  roles?: string[];
}

const NAV: NavItem[] = [
  { page: "dashboard", label: "Dashboard", icon: "grid" },
  { page: "generate", label: "Generate code", icon: "spark" },
  { page: "rules", label: "Coding rules", icon: "rules" },
  { page: "items", label: "Code registry", icon: "box" },
  { page: "audit", label: "Audit log", icon: "clock", roles: ["admin", "editor"] },
  { page: "settings", label: "Users & API keys", icon: "settings", roles: ["admin"] },
];

const TITLES: Record<Page, { title: string; subtitle: string }> = {
  dashboard: {
    title: "Dashboard",
    subtitle: "Coding activity across your PDM and ERP workflow.",
  },
  generate: {
    title: "Generate code",
    subtitle: "Guided numbering that follows your company standards.",
  },
  rules: {
    title: "Coding rules",
    subtitle: "Versioned rules shared by CAD, PDM, ERP and Office.",
  },
  "rule-editor": {
    title: "Rule editor",
    subtitle: "Compose segments, preview the format and publish a new version.",
  },
  items: {
    title: "Code registry",
    subtitle: "Every reserved code, its rule version and PDM/ERP reference.",
  },
  audit: {
    title: "Audit log",
    subtitle: "Who generated or changed what, and when.",
  },
  settings: {
    title: "Users & API keys",
    subtitle: "Access control and machine-to-machine credentials.",
  },
};

export function Layout({
  user,
  page,
  onNavigate,
  onLogout,
  children,
}: {
  user: User;
  page: Page;
  onNavigate: (page: Page) => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const meta = TITLES[page];
  const visibleNav = NAV.filter(
    (item) => !item.roles || item.roles.includes(user.role),
  );

  const navigate = (target: Page) => {
    onNavigate(target);
    setMobileOpen(false);
  };

  const initials = user.email.slice(0, 1).toUpperCase();

  return (
    <div className="app-shell">
      {mobileOpen ? (
        <div className="sidebar-backdrop" onClick={() => setMobileOpen(false)} />
      ) : null}
      <aside className={`sidebar${mobileOpen ? " sidebar-open" : ""}`}>
        <div className="brand" onClick={() => navigate("dashboard")}>
          <div className="brand-mark">
            <Icon name="spark" size={18} />
          </div>
          <div>
            <div className="brand-name">PartCode</div>
            <div className="brand-sub">Coding rules platform</div>
          </div>
        </div>

        <nav className="nav">
          <div className="nav-label">Workspace</div>
          {visibleNav.slice(0, 5).map((item) => (
            <button
              key={item.page}
              className={`nav-item${page === item.page ? " active" : ""}`}
              onClick={() => navigate(item.page)}
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
            </button>
          ))}
          {visibleNav.length > 5 ? <div className="nav-label">Administration</div> : null}
          {visibleNav.slice(5).map((item) => (
            <button
              key={item.page}
              className={`nav-item${page === item.page ? " active" : ""}`}
              onClick={() => navigate(item.page)}
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-card">
            <div className="avatar">{initials}</div>
            <div className="user-meta">
              <div className="user-email" title={user.email}>
                {user.email}
              </div>
              <div className="user-role">{titleCase(user.role)}</div>
            </div>
            <button className="icon-btn icon-btn-light" onClick={onLogout} title="Sign out">
              <Icon name="logout" size={16} />
            </button>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button
            className="icon-btn menu-btn"
            onClick={() => setMobileOpen((value) => !value)}
            aria-label="Toggle menu"
          >
            <Icon name="menu" />
          </button>
          <div>
            <h1>{meta.title}</h1>
            <p>{meta.subtitle}</p>
          </div>
          <div className="topbar-actions">
            <a className="btn btn-ghost btn-sm" href="/docs" target="_blank" rel="noreferrer">
              <Icon name="link" size={15} />
              API docs
            </a>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
