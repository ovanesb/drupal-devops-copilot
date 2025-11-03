"use client";
import * as React from "react";
import { cn } from "@/lib/utils";
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}
export const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, ...props }, ref) => (
    <input className={cn("flex h-9 w-full rounded-md border bg-background px-3 py-1 text-sm", className)} ref={ref} {...props} />
));
Input.displayName = "Input";
