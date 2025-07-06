import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils/cn'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-all duration-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-synthwave-cyan disabled:pointer-events-none disabled:opacity-50 font-cyber font-bold tracking-wider uppercase',
  {
    variants: {
      variant: {
        default:
          'bg-gradient-to-r from-synthwave-pink to-synthwave-cyan text-synthwave-dark shadow-neon-cyan hover:shadow-neon-pink hover:scale-105',
        destructive:
          'bg-synthwave-pink/80 text-synthwave-dark shadow-neon-pink hover:bg-synthwave-pink hover:shadow-neon-pink',
        outline:
          'border border-synthwave-cyan text-synthwave-cyan bg-transparent hover:bg-synthwave-cyan/20 hover:shadow-neon-cyan',
        secondary:
          'bg-synthwave-purple/80 text-synthwave-cyan hover:bg-synthwave-purple hover:shadow-neon-cyan',
        ghost: 
          'text-synthwave-cyan hover:bg-synthwave-cyan/20 hover:text-synthwave-pink hover:shadow-neon-pink',
        link: 
          'text-synthwave-pink underline-offset-4 hover:underline hover:text-synthwave-cyan hover:shadow-neon-cyan',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-10 rounded-md px-8',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants } 