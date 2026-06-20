# Grid Unlocked — local dev frontend image (production Dockerfile will differ)
FROM node:22-slim

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10 --activate

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY . .

ENV PORT=3000
EXPOSE 3000

CMD ["pnpm", "dev"]
