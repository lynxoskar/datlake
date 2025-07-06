'use client'

import { useUIStore } from '@/stores/ui-store-provider'
import { Menu, Search, Bell, Terminal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function Header() {
  const { toggleSidebar, searchTerm, setSearchTerm } = useUIStore(state => ({
    toggleSidebar: state.toggleSidebar,
    searchTerm: state.searchTerm,
    setSearchTerm: state.setSearchTerm,
  }))

  return (
    <header className="synthwave-card border-b border-synthwave-cyan/30 px-6 py-4 relative z-10">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="lg:hidden text-synthwave-cyan hover:text-synthwave-pink hover:bg-synthwave-purple/30 transition-all duration-300 hover:shadow-neon-pink"
          >
            <Menu className="h-5 w-5" />
          </Button>
          
          <div className="relative group">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-synthwave-cyan/50 group-focus-within:text-synthwave-pink transition-colors duration-300" />
            <Input
              type="search"
              placeholder="SEARCH SYSTEMS..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-80 pl-10 bg-synthwave-dark/50 border-synthwave-cyan/30 text-synthwave-cyan placeholder:text-synthwave-cyan/40 font-mono text-sm
                         focus:border-synthwave-pink focus:shadow-neon-pink focus:bg-synthwave-purple/20
                         transition-all duration-300"
            />
            <div className="absolute inset-0 rounded-md bg-gradient-to-r from-synthwave-cyan/10 to-synthwave-pink/10 opacity-0 group-focus-within:opacity-100 transition-opacity duration-300 pointer-events-none" />
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          {/* Status indicator */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-synthwave-dark/50 border border-synthwave-green/30 rounded-lg">
            <Terminal className="h-4 w-4 text-synthwave-green animate-pulse" />
            <span className="text-xs font-mono text-synthwave-green font-bold">ONLINE</span>
          </div>
          
          <Button 
            variant="ghost" 
            size="icon"
            className="text-synthwave-cyan hover:text-synthwave-pink hover:bg-synthwave-purple/30 transition-all duration-300 hover:shadow-neon-pink relative"
          >
            <Bell className="h-5 w-5" />
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-synthwave-pink rounded-full animate-pulse border border-synthwave-pink/50 shadow-neon-pink" />
          </Button>
          
          <div className="relative group">
            <div className="h-10 w-10 bg-gradient-to-br from-synthwave-pink to-synthwave-cyan rounded-lg flex items-center justify-center font-cyber font-bold text-synthwave-dark transition-all duration-300 group-hover:shadow-neon-cyan cursor-pointer">
              <span className="text-sm">U</span>
            </div>
            <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-synthwave-pink/20 to-synthwave-cyan/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300 animate-pulse" />
          </div>
        </div>
      </div>
      
      {/* Terminal command line effect */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-synthwave-cyan to-transparent animate-pulse" />
    </header>
  )
} 