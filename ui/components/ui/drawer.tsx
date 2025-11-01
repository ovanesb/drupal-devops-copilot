"use client";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";

export const Drawer = DialogPrimitive.Root;
export const DrawerTrigger = DialogPrimitive.Trigger;

export function DrawerContent({ children }: { children: React.ReactNode }) {
    return (
        <DialogPrimitive.Portal>
            <DialogPrimitive.Overlay className="fixed inset-0 bg-black/50" />
            <DialogPrimitive.Content className={cn("fixed inset-y-0 right-0 w-[420px] bg-card text-card-foreground shadow-xl p-0 outline-none")}>{children}</DialogPrimitive.Content>
        </DialogPrimitive.Portal>
    );
}
export function DrawerHeader({ children }: { children: React.ReactNode }) { return <div className="p-4 border-b">{children}</div>; }
export function DrawerTitle({ children }: { children: React.ReactNode }) { return <h2 className="text-base font-semibold">{children}</h2>; }
export function DrawerFooter({ children }: { children: React.ReactNode }) { return <div className="p-4 border-t flex gap-2 justify-end">{children}</div>; }