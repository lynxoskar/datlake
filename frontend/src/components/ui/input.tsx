import * as React from 'react'
import { cn } from '@/lib/utils/cn'

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'flex h-9 w-full rounded-md border px-3 py-1 text-sm shadow-sm transition-all duration-300',
          'bg-synthwave-dark/80 border-synthwave-cyan/30 text-synthwave-cyan',
          'font-mono placeholder:text-synthwave-cyan/40',
          'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-synthwave-pink',
          'focus-visible:border-synthwave-pink focus-visible:shadow-neon-pink',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'file:border-0 file:bg-transparent file:text-sm file:font-medium',
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = 'Input'

export { Input } 