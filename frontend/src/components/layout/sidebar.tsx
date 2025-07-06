'use client'

import { cn } from '@/lib/utils/cn'
import { useUIStore } from '@/stores/ui-store-provider'
import { 
  Database, 
  Table, 
  FolderOpen, 
  Home, 
  Settings, 
  X, 
  Menu 
} from 'lucide-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const navigationItems = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Jobs', href: '/jobs', icon: Database },
  { name: 'Datasets', href: '/datasets', icon: FolderOpen },
  { name: 'Tables', href: '/tables', icon: Table },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useUIStore(state => ({
    sidebarOpen: state.sidebarOpen,
    toggleSidebar: state.toggleSidebar,
  }))
  
  const pathname = usePathname()

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 lg:hidden"
          onClick={toggleSidebar}
        />
      )}
      
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 h-full w-64 synthwave-card border-r border-synthwave-cyan/30 transform transition-all duration-300 ease-in-out z-50 lg:translate-x-0 lg:static lg:z-0',
          'before:absolute before:inset-0 before:bg-gradient-to-b before:from-synthwave-purple/20 before:to-synthwave-dark/80 before:backdrop-blur-xl before:-z-10',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between p-4 border-b border-synthwave-cyan/30">
          <h2 className="text-xl font-cyber font-bold text-neon-cyan animate-pulse-neon">
            DUCKLAKE
          </h2>
          <button
            onClick={toggleSidebar}
            className="p-2 hover:bg-synthwave-purple/30 rounded-lg lg:hidden transition-all duration-300 hover:shadow-neon-cyan"
          >
            <X className="h-5 w-5 text-synthwave-cyan" />
          </button>
        </div>
        
        <nav className="p-4">
          <ul className="space-y-2">
            {navigationItems.map((item) => {
              const isActive = pathname === item.href
              return (
                <li key={item.name}>
                  <Link
                    href={item.href}
                    className={cn(
                      'flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-mono font-medium transition-all duration-300 group relative overflow-hidden',
                      isActive
                        ? 'bg-synthwave-cyan/20 text-synthwave-cyan border border-synthwave-cyan/50 shadow-neon-cyan animate-glow'
                        : 'text-synthwave-cyan/70 hover:text-synthwave-pink hover:bg-synthwave-purple/20 hover:border-synthwave-pink/30 border border-transparent'
                    )}
                  >
                    <item.icon className={cn(
                      "h-5 w-5 transition-all duration-300",
                      isActive ? "text-synthwave-cyan animate-pulse" : "group-hover:text-synthwave-pink"
                    )} />
                    <span className={cn(
                      "transition-all duration-300",
                      isActive ? "text-shadow-lg" : "group-hover:text-shadow-md"
                    )}>
                      {item.name.toUpperCase()}
                    </span>
                    {isActive && (
                      <div className="absolute inset-0 bg-gradient-to-r from-synthwave-cyan/10 to-synthwave-pink/10 animate-pulse" />
                    )}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
        
        {/* Terminal status indicator */}
        <div className="absolute bottom-4 left-4 right-4">
          <div className="terminal p-3 rounded-lg">
            <div className="terminal-content">
              <div className="flex items-center gap-2 text-xs font-mono">
                <div className="w-2 h-2 bg-synthwave-green rounded-full animate-pulse"></div>
                <span className="text-synthwave-green">SYSTEM ONLINE</span>
              </div>
              <div className="text-xs text-synthwave-cyan/60 mt-1 font-mono">
                {new Date().toLocaleTimeString()}
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
} 