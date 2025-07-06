import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils/cn'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-synthwave-cyan/20 text-synthwave-cyan border-synthwave-cyan/50 shadow-neon-cyan',
        secondary:
          'border-transparent bg-synthwave-purple/20 text-synthwave-pink border-synthwave-pink/50',
        destructive:
          'border-transparent bg-synthwave-pink/20 text-synthwave-pink border-synthwave-pink/50 shadow-neon-pink',
        outline: 'text-synthwave-cyan border-synthwave-cyan/50',
        success:
          'border-transparent bg-synthwave-green/20 text-synthwave-green border-synthwave-green/50 shadow-neon-green',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div 
      className={cn(
        badgeVariants({ variant }), 
        'font-mono font-bold tracking-wider',
        className
      )} 
      {...props} 
    />
  )
}

export { Badge, badgeVariants } 