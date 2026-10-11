import React from "react";
import { cn } from "../../lib/utils";
import { AlertCircle, CheckCircle2, Info, AlertTriangle } from "lucide-react";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "success" | "warning" | "destructive";
  title?: string;
}

export const Alert: React.FC<AlertProps> = ({
  className,
  variant = "info",
  title,
  children,
  ...props
}) => {
  const variantStyles = {
    info: "bg-blue-50 text-blue-900 border-blue-200 dark:bg-blue-950/40 dark:text-blue-200 dark:border-blue-900",
    success: "bg-emerald-50 text-emerald-900 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:border-emerald-900",
    warning: "bg-amber-50 text-amber-900 border-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-900",
    destructive: "bg-rose-50 text-rose-900 border-rose-200 dark:bg-rose-950/40 dark:text-rose-200 dark:border-rose-900",
  };

  const icons = {
    info: <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0" />,
    success: <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />,
    warning: <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />,
    destructive: <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />,
  };

  return (
    <div
      role="alert"
      className={cn(
        "flex gap-3 p-4 rounded-xl border text-sm leading-relaxed",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {icons[variant]}
      <div className="flex-1">
        {title && <h5 className="font-semibold mb-1 leading-snug">{title}</h5>}
        <div>{children}</div>
      </div>
    </div>
  );
};
