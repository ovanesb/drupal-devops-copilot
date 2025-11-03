# ===== Build Next.js =====
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN \
  if [ -f pnpm-lock.yaml ]; then npm i -g pnpm && pnpm i --frozen-lockfile; \
  elif [ -f yarn.lock ]; then yarn --frozen-lockfile; \
  else npm ci; fi

FROM node:20-alpine AS build
WORKDIR /app

# ---- Bake public env at build time (used by the browser) ----
# Primary (Sprint 2) base used by our hooks: api.ts -> NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000/api
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}

# Legacy var you already had in compose; keep it for compatibility if other code reads it
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY --from=deps /app/node_modules ./node_modules
# ui/ is the Next.js app directory (compose builds with context=./ui)
COPY . .

# Optional: disable telemetry in CI/builds
ENV NEXT_TELEMETRY_DISABLED=1

RUN \
  if [ -f package.json ]; then \
    [ -f pnpm-lock.yaml ] && pnpm build || \
    ([ -f yarn.lock ] && yarn build) || \
    npm run build; \
  fi

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOST=0.0.0.0

# Re-expose the public env at runtime (helps with runtime tools, though Next bakes it at build)
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY --from=build /app ./
EXPOSE 3000
CMD ["npm","run","start"]
