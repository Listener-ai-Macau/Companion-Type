// Adapted from Shadcn Dashboard's MIT-licensed card component.
// Copyright (c) 2026 Shadcn Dashboard; full notice is in ThirdPartyNotices.txt.
import { forwardRef, type ComponentPropsWithoutRef } from 'react';

export const CompanionCard = forwardRef<HTMLElement, ComponentPropsWithoutRef<'section'>>(
  function CompanionCard({ className = '', ...props }, ref) {
    return <section ref={ref} data-slot="card" className={`companion-card ${className}`} {...props} />;
  },
);
