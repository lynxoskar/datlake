import { createStore } from 'zustand/vanilla'
import { immer } from 'zustand/middleware/immer'

export type UIState = {
  sidebarOpen: boolean
  currentView: 'jobs' | 'datasets' | 'tables' | 'dashboard'
  searchTerm: string
  selectedItems: Set<string>
  theme: 'light' | 'dark'
  notifications: Array<{
    id: string
    type: 'success' | 'error' | 'warning' | 'info'
    title: string
    message: string
    timestamp: string
  }>
}

export type UIActions = {
  toggleSidebar: () => void
  setCurrentView: (view: UIState['currentView']) => void
  setSearchTerm: (term: string) => void
  toggleSelectedItem: (id: string) => void
  clearSelection: () => void
  setTheme: (theme: UIState['theme']) => void
  addNotification: (notification: Omit<UIState['notifications'][0], 'id' | 'timestamp'>) => void
  removeNotification: (id: string) => void
  clearNotifications: () => void
}

export type UIStore = UIState & UIActions

export const defaultUIState: UIState = {
  sidebarOpen: true,
  currentView: 'dashboard',
  searchTerm: '',
  selectedItems: new Set(),
  theme: 'light',
  notifications: [],
}

export const createUIStore = (initState: Partial<UIState> = {}) => {
  return createStore<UIStore>()(
    immer((set, get) => ({
      ...defaultUIState,
      ...initState,
      toggleSidebar: () => set(state => {
        state.sidebarOpen = !state.sidebarOpen
      }),
      setCurrentView: (view) => set(state => {
        state.currentView = view
      }),
      setSearchTerm: (term) => set(state => {
        state.searchTerm = term
      }),
      toggleSelectedItem: (id) => set(state => {
        if (state.selectedItems.has(id)) {
          state.selectedItems.delete(id)
        } else {
          state.selectedItems.add(id)
        }
      }),
      clearSelection: () => set(state => {
        state.selectedItems.clear()
      }),
      setTheme: (theme) => set(state => {
        state.theme = theme
      }),
      addNotification: (notification) => set(state => {
        const id = Math.random().toString(36).substring(2, 9)
        const timestamp = new Date().toISOString()
        state.notifications.push({
          ...notification,
          id,
          timestamp,
        })
      }),
      removeNotification: (id) => set(state => {
        state.notifications = state.notifications.filter(n => n.id !== id)
      }),
      clearNotifications: () => set(state => {
        state.notifications = []
      }),
    }))
  )
} 