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
COPY --from=deps /app/node_modules ./node_modules
# ui/ is the Next.js app directory (compose builds with context=./ui)
COPY . .
RUN \
  if [ -f package.json ]; then \
    [ -f pnpm-lock.yaml ] && pnpm build || \
    ([ -f yarn.lock ] && yarn build) || \
    npm run build; \
  fi

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
EXPOSE 3000
CMD ["npm","run","start"]
