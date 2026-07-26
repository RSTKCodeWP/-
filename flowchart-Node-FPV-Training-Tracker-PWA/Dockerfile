FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --production

COPY src/ src/
COPY public/ public/

RUN mkdir -p /app/data

EXPOSE 3000

ENV NODE_ENV=production
ENV DB_PATH=/app/data/flowchart.db

CMD ["node", "--import", "tsx", "src/server.ts"]
