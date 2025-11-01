"use client";
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter } from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useFlowStore } from "@/lib/store";
import { v4 as uuid } from "uuid";
import * as React from "react";

const ProfileSchema = z.object({
    id: z.string().optional(),
    name: z.string().min(2, "Name is required"),
    kind: z.enum(["jira", "gitlab", "acquia", "generic"]),
    baseUrl: z.string().url("Must be a valid URL").optional().or(z.literal("")),
    username: z.string().optional(),
});

type ProfileForm = z.infer<typeof ProfileSchema>;

type Props = {
    open: boolean;
    onOpenChange: (v: boolean) => void;
    defaultKind?: "jira" | "gitlab" | "acquia" | "generic";
};

export function IntegrationProfileDrawer({ open, onOpenChange, defaultKind = "jira" }: Props) {
    const { addProfile } = useFlowStore();

    const { register, handleSubmit, formState: { errors }, reset, setValue } = useForm<ProfileForm>({
        resolver: zodResolver(ProfileSchema),
        defaultValues: { kind: defaultKind, name: "", baseUrl: "", username: "" },
    });

    // keep kind in sync if parent wants a different default later
    React.useEffect(() => {
        setValue("kind", defaultKind);
    }, [defaultKind, setValue]);

    const onSubmit = (data: ProfileForm) => {
        const id = uuid(); // safer than crypto.randomUUID()
        addProfile({ ...data, id });
        reset({ kind: defaultKind, name: "", baseUrl: "", username: "" });
        onOpenChange(false);
    };

    return (
        <Drawer open={open} onOpenChange={onOpenChange}>
            <DrawerContent>
                <DrawerHeader>
                    <DrawerTitle>Create Integration Profile</DrawerTitle>
                </DrawerHeader>

                <form onSubmit={handleSubmit(onSubmit)} className="p-4 space-y-3">
                    <div>
                        <Label htmlFor="name">Name</Label>
                        <Input id="name" {...register("name")} />
                        {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
                    </div>

                    <div>
                        <Label htmlFor="kind">Kind</Label>
                        <Input
                            id="kind"
                            placeholder="jira | gitlab | acquia | generic"
                            {...register("kind")}
                        />
                        {errors.kind && <p className="text-sm text-destructive">{errors.kind.message}</p>}
                    </div>

                    <div>
                        <Label htmlFor="baseUrl">Base URL</Label>
                        <Input id="baseUrl" placeholder="https://your-instance" {...register("baseUrl")} />
                        {errors.baseUrl && <p className="text-sm text-destructive">{errors.baseUrl.message}</p>}
                    </div>

                    <div>
                        <Label htmlFor="username">Username</Label>
                        <Input id="username" placeholder="bot@example.com" {...register("username")} />
                    </div>

                    <DrawerFooter>
                        <Button type="submit">Save profile</Button>
                        <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
                    </DrawerFooter>
                </form>
            </DrawerContent>
        </Drawer>
    );
}
