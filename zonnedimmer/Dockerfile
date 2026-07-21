ARG BUILD_FROM
FROM $BUILD_FROM

# Basis packages voor Chromium en Node.js
RUN apk add --no-cache \
    nodejs \
    npm \
    npx \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ttf-freefont \
    font-noto-emoji \
    && rm -rf /var/cache/apk/*

# Zorg dat Playwright de systeem Chromium gebruikt
ENV PLAYWRIGHT_BROWSERS_PATH=0
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV CHROME_BIN=/usr/bin/chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

WORKDIR /app

# Installeer dependencies eerst voor betere Docker layer caching
COPY app/package.json ./
RUN npm install --omit=dev && npm cache clean --force

# Kopieer applicatie code
COPY app/ ./

# Maak run.sh uitvoerbaar
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Persistente data map
VOLUME /data
RUN mkdir -p /data/browser-profile

EXPOSE 8099

CMD ["/run.sh"]
