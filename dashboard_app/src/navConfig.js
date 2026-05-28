import {
  LayoutDashboard,
  Receipt,
  Sparkles,
  Wallet,
  ArrowLeftRight,
  PiggyBank,
  Tag,
  Users,
  Settings,
} from 'lucide-react';

export const SIDEBAR_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, adminOnly: true },
  { id: 'chiusure', label: 'Chiusure Cassa', icon: Receipt, adminOnly: true },
  { id: 'acquisisci-ai', label: 'Acquisisci con IA', icon: Sparkles, adminOnly: false },
  { id: 'versamenti', label: 'Versamenti', icon: Wallet, adminOnly: false },
  { id: 'movimenti', label: 'Movimenti', icon: ArrowLeftRight, adminOnly: false },
  { id: 'fondo-cassa', label: 'Fondo Cassa', icon: PiggyBank, adminOnly: false },
  { id: 'reparti', label: 'Reparti', icon: Tag, adminOnly: true },
  { id: 'utenti', label: 'Utenti', icon: Users, adminOnly: true },
  { id: 'impostazioni', label: 'Impostazioni', icon: Settings, adminOnly: false, pushToBottom: true },
];

export function getDefaultSidebarMenu(role) {
  const isAdmin = role === 'amministratore';
  return SIDEBAR_ITEMS
    .filter(item => isAdmin || !item.adminOnly)
    .map(item => item.id);
}

export function normalizeSidebarMenu(role, menuIds) {
  const allIds = new Set(SIDEBAR_ITEMS.map(item => item.id));
  const selected = (menuIds || []).filter(id => allIds.has(id));
  if (!selected.length) return getDefaultSidebarMenu(role);
  return SIDEBAR_ITEMS.map(item => item.id).filter(id => selected.includes(id));
}

export function getVisibleNavItems(role, menuIds) {
  const normalized = normalizeSidebarMenu(role, menuIds ?? getDefaultSidebarMenu(role));
  const byId = Object.fromEntries(SIDEBAR_ITEMS.map(item => [item.id, item]));
  return normalized.map(id => byId[id]).filter(Boolean);
}

export function canAccessView(role, menuIds, viewId) {
  return getVisibleNavItems(role, menuIds).some(item => item.id === viewId);
}
