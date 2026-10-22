import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Buttons are intentionally large: the youngest users are 6–7 years old.
 * Minimum touch target is 44px (size "default"); the hero actions use "xl".
 * Pass `render={<Link href="…" />}` to render a link with button styling.
 */
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center gap-2 rounded-full border border-transparent bg-clip-padding font-semibold whitespace-nowrap transition-all outline-none select-none focus-visible:ring-4 focus-visible:ring-ring/30 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-5",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-float hover:bg-primary/90",
        lime: "bg-lime text-ink hover:bg-lime-deep",
        outline: "border-primary/60 bg-transparent text-primary hover:bg-teal-soft",
        secondary: "bg-teal-soft text-primary hover:bg-sage/60",
        ghost: "text-foreground hover:bg-muted",
        soft: "bg-white text-ink shadow-card ring-1 ring-line hover:bg-muted",
        destructive: "bg-destructive/10 text-destructive hover:bg-destructive/15",
        link: "h-auto rounded-none px-0 text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-11 px-5 text-base",
        sm: "h-9 px-4 text-sm [&_svg:not([class*='size-'])]:size-4",
        lg: "h-12 px-6 text-base",
        xl: "h-14 px-7 text-lg",
        icon: "size-11",
        "icon-sm": "size-9 [&_svg:not([class*='size-'])]:size-4",
        "icon-lg": "size-14 [&_svg:not([class*='size-'])]:size-6",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  nativeButton,
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      nativeButton={nativeButton ?? props.render === undefined}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
