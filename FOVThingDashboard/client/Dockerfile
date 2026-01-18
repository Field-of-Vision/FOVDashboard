# client/Dockerfile
FROM node:18-alpine
WORKDIR /app

# Build-time env for CRA (used at build time)
ARG REACT_APP_API_BASE
ARG REACT_APP_WS_BASE
ENV REACT_APP_API_BASE=$REACT_APP_API_BASE
ENV REACT_APP_WS_BASE=$REACT_APP_WS_BASE

# Install deps using lockfile
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund

# Copy source and build
COPY . .
RUN npm run build

# Serve static build
RUN npm i -g serve
EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000"]
