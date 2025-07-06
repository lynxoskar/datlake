'use client'

import { type ReactNode, createContext, useRef, useContext } from 'react'
import { type StoreApi, useStore } from 'zustand'
import { type UIStore, createUIStore, type UIState } from './ui-store'

export const UIStoreContext = createContext<StoreApi<UIStore> | undefined>(undefined)

export interface UIStoreProviderProps {
  children: ReactNode
  initialState?: Partial<UIState>
}

export function UIStoreProvider({ children, initialState }: UIStoreProviderProps) {
  const storeRef = useRef<StoreApi<UIStore>>()
  if (!storeRef.current) {
    storeRef.current = createUIStore(initialState)
  }

  return (
    <UIStoreContext.Provider value={storeRef.current}>
      {children}
    </UIStoreContext.Provider>
  )
}

export const useUIStore = <T,>(selector: (store: UIStore) => T): T => {
  const context = useContext(UIStoreContext)
  if (!context) {
    throw new Error('useUIStore must be used within a UIStoreProvider')
  }
  return useStore(context, selector)
} 