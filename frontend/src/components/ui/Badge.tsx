import React from "react";
import { cn } from "../../lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "secondary" | "outline" | "success" | "warning" | "destructive" | "info";
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = "default",
  children,
  ...props
}) => {
  const variantStyles = {
    default: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:border-blue-800",
    secondary: "bg-slate-100 text-slate-800 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
    outline: "text-slate-700 border-slate-300 dark:text-slate-300 dark:border-slate-700",
    success: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:border-emerald-800",
    warning: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950/50 dark:text-amber-400 dark:border-amber-800",
    destructive: "bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-950/50 dark:text-rose-400 dark:border-rose-800",
    info: "bg-sky-100 text-sky-800 border-sky-200 dark:bg-sky-950/50 dark:text-sky-400 dark:border-sky-800",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border transition-colors",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
