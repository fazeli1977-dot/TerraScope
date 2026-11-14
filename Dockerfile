FROM node:20-slim

# Install Python 3 + venv for the ecological AI engine
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY . .

RUN python3 -m venv .venv \
    && .venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PORT=10000
EXPOSE 10000

CMD ["node", "server.js"]