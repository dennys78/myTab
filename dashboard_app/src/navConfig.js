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
  { id: 'impostazioni', label: 'Impostazioni', icon: Settings, adminOnly: true },
];

export function getVisibleNavItems(role) {
  const isAdmin = role === 'amministratore';
  return SIDEBAR_ITEMS.filter(item => isAdmin || !item.adminOnly);
}
