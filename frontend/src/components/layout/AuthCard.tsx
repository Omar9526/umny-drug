import Link from "next/link";
import { Logo } from "@/components/brand/Logo";
import { cn } from "@/lib/utils";

/** Centered single-column frame for welcome/auth screens (mobile-first, comfortable on desktop). */
export function AuthCard({
  title,
  subtitle,
  children,
  footer,
  className,
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="flex min-h-dvh flex-col items-center px-4 py-6 sm:justify-center">
      <Link href="/" className="mb-6 self-start sm:self-center" aria-label="На главную">
        <Logo />
      </Link>
      <section className={cn("w-full max-w-md rounded-[28px] bg-white p-6 shadow-card sm:p-8", className)}>
        {title && <h1 className="text-2xl font-extrabold">{title}</h1>}
        {subtitle && <p className="mt-1 text-base text-muted-foreground">{subtitle}</p>}
        <div className={cn(title && "mt-6")}>{children}</div>
      </section>
      {footer && <div className="mt-6 w-full max-w-md text-center text-base text-muted-foreground">{footer}</div>}
    </div>
  );
}
