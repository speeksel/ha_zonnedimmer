'use strict';

const express = require('express');
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// ─── Configuration from add-on environment ─────────────────────────
const PORT = 8099;
const PROFILE_DIR = '/data/browser-profile';
const STATE_FILE = '/data/state.json';
const ZONNEDIMMER_URL = process.env.ZONNEDIMMER_URL || 'https://app.zonnedimmer.nl';
const HEADLESS = process.env.ZONNEDIMMER_HEADLESS !== 'false';
const COOLDOWN_MS = (parseInt(process.env.ZONNEDIMMER_COOLDOWN_MINUTES || '5', 10)) * 60 * 1000;
const BROWSER_TIMEOUT_MS = parseInt(process.env.ZONNEDIMMER_TIMEOUT_MS || '60000', 10);
const LOGIN_CHECK_MS = (parseInt(process.env.ZONNEDIMMER_LOGIN_CHECK_MINUTES || '60', 10)) * 60 * 1000;
const CHROMIUM_PATH = process.env.CHROME_BIN || '/usr/bin/chromium';
const LOG_LEVEL = process.env.ZONNEDIMMER_LOG_LEVEL || 'info';
const CONFIG_USERNAME = process.env.ZONNEDIMMER_USERNAME || '';
const CONFIG_PASSWORD = process.env.ZONNEDIMMER_PASSWORD || '';

const LOG_LEVELS = { debug: 0, info: 1, warning: 2, error: 3 };

// ─── Logging ──────────────────────────────────────────────────────
function log(level, message) {
  if (LOG_LEVELS[level] >= (LOG_LEVELS[LOG_LEVEL] ?? 1)) {
    const ts = new Date().toISOString();
    console.log(`[${ts}] [${level.toUpperCase()}] ${message}`);
  }
}

// ─── Persistent state ─────────────────────────────────────────────
function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    }
  } catch (e) {
    log('warning', `Kon state niet laden: ${e.message}`);
  }
  return {
    lastActionTime: 0,
    lastActionResult: null,
    loginRequired: true,
    lastLoginCheck: 0,
  };
}

function saveState(updates) {
  try {
    const current = loadState();
    const next = { ...current, ...updates };
    fs.writeFileSync(STATE_FILE, JSON.stringify(next, null, 2));
    log('debug', 'State opgeslagen');
  } catch (e) {
    log('error', `Kon state niet opslaan: ${e.message}`);
  }
}

function getState() {
  return loadState();
}

// ─── Mutex / Lock ─────────────────────────────────────────────────
let browserInUse = false;

async function withLock(fn) {
  if (browserInUse) {
    return {
      success: false,
      error: 'Een andere browseractie is al bezig. Probeer het later opnieuw.',
      status: 'busy',
    };
  }
  browserInUse = true;
  try {
    return await fn();
  } finally {
    browserInUse = false;
  }
}

function isCoolingDown() {
  const state = getState();
  if (!state.lastActionTime) return false;
  const elapsed = Date.now() - state.lastActionTime;
  return elapsed < COOLDOWN_MS;
}

function cooldownRemaining() {
  const state = getState();
  if (!state.lastActionTime) return 0;
  const remaining = COOLDOWN_MS - (Date.now() - state.lastActionTime);
  return Math.max(0, Math.ceil(remaining / 1000));
}

// ─── Browser automation ────────────────────────────────────────────
async function launchBrowserContext() {
  log('debug', `Browser starten (headless=${HEADLESS}, executable=${CHROMIUM_PATH})`);
  const context = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: HEADLESS,
    executablePath: CHROMIUM_PATH,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--disable-features=VizDisplayCompositor',
      '--font-render-hinting=none',
    ],
    viewport: { width: 1280, height: 720 },
    locale: 'nl-NL',
    timezoneId: 'Europe/Amsterdam',
  });
  return context;
}

async function checkLoggedIn(page) {
  try {
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    const loginElements = await page
      .locator('input[type="password"], input[name="username"], button:has-text("Inloggen"), button:has-text("Log in"), button:has-text("Sign in")')
      .count();
    return loginElements === 0;
  } catch {
    return false;
  }
}

async function attemptLogin(page, username, password) {
  log('info', 'Probeer in te loggen met opgegeven referenties...');

  // Vul gebruikersnaam in
  const usernameInput = page.locator('input[type="email"], input[name="username"], input[name="email"], input[id="username"], input[id="email"]').first();
  await usernameInput.waitFor({ state: 'visible', timeout: 10000 });
  await usernameInput.fill(username);

  // Vul wachtwoord in
  const passwordInput = page.locator('input[type="password"], input[name="password"], input[id="password"]').first();
  await passwordInput.waitFor({ state: 'visible', timeout: 5000 });
  await passwordInput.fill(password);

  // Klik op inlogknop
  const loginButton = page.locator('button:has-text("Inloggen"), button:has-text("Log in"), button:has-text("Sign in"), button[type="submit"]').first();
  await loginButton.click();

  // Wacht tot pagina geladen is
  await page.waitForLoadState('networkidle', { timeout: BROWSER_TIMEOUT_MS });

  // Controleer of login succesvol was
  const stillOnLogin = await page
    .locator('input[type="password"]')
    .count();

  if (stillOnLogin > 0) {
    throw new Error('Login mislukt - controleer gebruikersnaam en wachtwoord');
  }

  log('info', 'Login succesvol, sessie opgeslagen in persistent profiel');
  saveState({ loginRequired: false, lastLoginCheck: Date.now() });
  return true;
}

// Toegestane dim-duren in uren (overeenkomend met de knoppen op de instellingenpagina).
const ALLOWED_DURATIONS = [1, 2, 4, 8];

async function performTurnOff(durationHours) {
  let context = null;
  try {
    context = await launchBrowserContext();
    const page = await context.newPage();

    const settingsUrl = `${ZONNEDIMMER_URL}/dashboard/settings`;
    log('info', `Navigeren naar ${settingsUrl}`);
    await page.goto(settingsUrl, { waitUntil: 'networkidle', timeout: BROWSER_TIMEOUT_MS });

    // Controleer login status
    const loggedIn = await checkLoggedIn(page);

    if (!loggedIn) {
      log('warning', 'Niet ingelogd, probeer automatische login');
      if (CONFIG_USERNAME && CONFIG_PASSWORD) {
        await attemptLogin(page, CONFIG_USERNAME, CONFIG_PASSWORD);
        log('info', `Opnieuw navigeren naar ${settingsUrl} na login`);
        await page.goto(settingsUrl, { waitUntil: 'networkidle', timeout: BROWSER_TIMEOUT_MS });
      } else {
        saveState({ loginRequired: true });
        return {
          success: false,
          status: 'login_required',
          error: 'Sessie verlopen en geen referenties opgegeven. Log handmatig in via de Ingress-pagina.',
          timestamp: new Date().toISOString(),
        };
      }
    }

    // Zoek de knop voor de gevraagde duur (bijv. "2 uur uitzetten")
    const buttonText = `${durationHours} uur uitzetten`;
    log('info', `Zoeken naar de knop "${buttonText}"`);
    const button = page.locator(`button:has-text("${buttonText}")`).first();
    const buttonCount = await button.count();

    if (buttonCount === 0) {
      log('error', `Knop "${buttonText}" niet gevonden op de pagina`);
      return {
        success: false,
        status: 'button_not_found',
        error: `De knop "${buttonText}" is niet gevonden op de Zonnedimmer-instellingenpagina.`,
        pageUrl: page.url(),
        timestamp: new Date().toISOString(),
      };
    }

    // Accepteer de JavaScript confirm()-dialoog automatisch (de knop vraagt om bevestiging).
    page.on('dialog', async (dialog) => {
      log('debug', `Dialoog geaccepteerd: "${dialog.message()}"`);
      try {
        await dialog.accept();
      } catch (e) {
        log('warning', `Kon dialoog niet accepteren: ${e.message}`);
      }
    });

    // Wacht op de response van de form submission (POST /dashboard/manual-power-control).
    const responsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/dashboard/manual-power-control'),
      { timeout: BROWSER_TIMEOUT_MS }
    );

    await button.click({ timeout: BROWSER_TIMEOUT_MS });

    const response = await responsePromise;
    const httpStatus = response.status();
    log('debug', `Form submission HTTP-status: ${httpStatus}`);

    // Wacht tot de pagina weer stabiel is na de submit.
    await page.waitForLoadState('networkidle', { timeout: BROWSER_TIMEOUT_MS }).catch(() => {});

    if (httpStatus >= 400) {
      log('error', `Dimmen mislukt, HTTP-status ${httpStatus}`);
      return {
        success: false,
        status: 'failed',
        error: `Zonnedimmer retourneerde HTTP-status ${httpStatus} bij het dimmen.`,
        httpStatus,
        pageUrl: page.url(),
        timestamp: new Date().toISOString(),
      };
    }

    log('info', `Actie uitgevoerd: knop "${buttonText}" geklikt (HTTP ${httpStatus})`);
    return buildSuccess(durationHours, buttonText);
  } catch (error) {
    log('error', `Fout bij uitvoeren actie: ${error.message}`);
    return {
      success: false,
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  } finally {
    if (context) {
      try {
        await context.close();
      } catch (e) {
        log('warning', `Kon browser context niet sluiten: ${e.message}`);
      }
    }
  }
}

function buildSuccess(durationHours, buttonText) {
  const result = {
    success: true,
    status: 'completed',
    durationHours,
    message: `Zonnedimmer uitgeschakeld voor ${durationHours} uur (knop: "${buttonText}").`,
    timestamp: new Date().toISOString(),
  };
  saveState({
    lastActionTime: Date.now(),
    lastActionResult: result,
    loginRequired: false,
    lastLoginCheck: Date.now(),
  });
  return result;
}

// ─── Login check interval ────────────────────────────────────────
async function periodicLoginCheck() {
  if (browserInUse) return;
  const state = getState();
  if (Date.now() - (state.lastLoginCheck || 0) < LOGIN_CHECK_MS) return;

  log('debug', 'Periodieke login-controle gestart');
  let context = null;
  try {
    context = await launchBrowserContext();
    const page = await context.newPage();
    await page.goto(ZONNEDIMMER_URL, { waitUntil: 'networkidle', timeout: BROWSER_TIMEOUT_MS });
    const loggedIn = await checkLoggedIn(page);
    saveState({ loginRequired: !loggedIn, lastLoginCheck: Date.now() });
    if (!loggedIn) {
      log('warning', 'Login verlopen - herinloggen vereist');
    }
  } catch (e) {
    log('warning', `Login-controle mislukt: ${e.message}`);
  } finally {
    if (context) {
      try {
        await context.close();
      } catch {}
    }
  }
}

setInterval(periodicLoginCheck, Math.min(LOGIN_CHECK_MS, 10 * 60 * 1000));

// ─── Ingress admin page ──────────────────────────────────────────
function getIngressHtml() {
  const state = getState();
  const loginStatus = state.loginRequired
    ? '<span class="bad">❌ Herinloggen vereist</span>'
    : '<span class="good">✅ Ingelogd</span>';
  const lastAction = state.lastActionResult
    ? `<pre>${JSON.stringify(state.lastActionResult, null, 2)}</pre>`
    : '<p>Geen actie uitgevoerd.</p>';
  const cdRemaining = cooldownRemaining();
  const cooldownText = cdRemaining > 0
    ? `<span class="warn">Cooldown: ${cdRemaining}s resterend</span>`
    : '<span class="good">Klaar voor actie</span>';

  return `<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Zonnedimmer Add-on</title>
  <style>
    body { font-family: sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.5rem; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
    .good { color: #2e7d32; }
    .bad { color: #c62828; }
    .warn { color: #f57f17; }
    pre { background: #f5f5f5; padding: 0.5rem; border-radius: 4px; overflow-x: auto; }
    button { padding: 0.5rem 1rem; font-size: 1rem; cursor: pointer; border-radius: 4px; border: none; }
    .btn-primary { background: #03a9f4; color: #fff; }
    .btn-warn { background: #ff9800; color: #fff; }
    .button-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem; }
    #result { margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>Zonnedimmer Add-on</h1>

  <div class="card">
    <h2>Status</h2>
    <p>Login: ${loginStatus}</p>
    <p>${cooldownText}</p>
    <p>Laatste actie:</p>
    ${lastAction}
  </div>

  <div class="card">
    <h2>Acties</h2>
    <div class="button-row">
      <button class="btn-primary" onclick="doAction(1)">1 uur uitzetten</button>
      <button class="btn-primary" onclick="doAction(2)">2 uur uitzetten</button>
      <button class="btn-primary" onclick="doAction(4)">4 uur uitzetten</button>
      <button class="btn-primary" onclick="doAction(8)">8 uur uitzetten</button>
    </div>
    <button class="btn-warn" onclick="doLogin()">Inloggen</button>
    <div id="result"></div>
  </div>

  <div class="card">
    <h2>Configuratie</h2>
    <p>URL: ${ZONNEDIMMER_URL}</p>
    <p>Headless: ${HEADLESS}</p>
    <p>Cooldown: ${COOLDOWN_MS / 60000} minuten</p>
    <p>Profielmap: ${PROFILE_DIR}</p>
  </div>

  <script>
    async function doAction(duration) {
      document.getElementById('result').innerHTML = '<p>Bezig met ' + duration + ' uur uitzetten...</p>';
      try {
        const res = await fetch('/turn-off', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ duration: duration })
        });
        const data = await res.json();
        document.getElementById('result').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
      } catch (e) {
        document.getElementById('result').innerHTML = '<p class="bad">Fout: ' + e.message + '</p>';
      }
    }
    async function doLogin() {
      document.getElementById('result').innerHTML = '<p>Login bezig...</p>';
      try {
        const res = await fetch('/login', { method: 'POST' });
        const data = await res.json();
        document.getElementById('result').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
      } catch (e) {
        document.getElementById('result').innerHTML = '<p class="bad">Fout: ' + e.message + '</p>';
      }
    }
  </script>
</body>
</html>`;
}

// ─── Express app ─────────────────────────────────────────────────
const app = express();
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Ingress admin page
app.get('/ingress', (req, res) => {
  res.type('html').send(getIngressHtml());
});
app.get('/', (req, res) => {
  res.type('html').send(getIngressHtml());
});

// Status endpoint
app.get('/status', (req, res) => {
  const state = getState();
  res.json({
    status: 'ok',
    loginRequired: state.loginRequired,
    lastActionTime: state.lastActionTime ? new Date(state.lastActionTime).toISOString() : null,
    lastActionResult: state.lastActionResult,
    cooldownRemainingSeconds: cooldownRemaining(),
    busy: browserInUse,
  });
});

// Main action: turn off for a given number of hours (1, 2, 4 or 8)
app.post('/turn-off', async (req, res) => {
  // Accepteer duration uit JSON body of query string
  const rawDuration = req.body?.duration ?? req.query?.duration;
  const duration = parseInt(rawDuration, 10);

  log('info', `POST /turn-off ontvangen (duration=${rawDuration})`);

  if (!ALLOWED_DURATIONS.includes(duration)) {
    log('warning', `Ongeldige duur ontvangen: ${rawDuration}`);
    return res.status(400).json({
      success: false,
      status: 'invalid_duration',
      error: `Ongeldige duur. Toegestaan: ${ALLOWED_DURATIONS.join(', ')} uur.`,
      allowedDurations: ALLOWED_DURATIONS,
      timestamp: new Date().toISOString(),
    });
  }

  // Cooldown check
  if (isCoolingDown()) {
    const remaining = cooldownRemaining();
    log('warning', `Aanvraag afgewezen - cooldown actief (${remaining}s resterend)`);
    return res.status(429).json({
      success: false,
      status: 'cooldown',
      error: `Cooldown actief. Probeer opnieuw over ${remaining} seconden.`,
      cooldownRemainingSeconds: remaining,
      timestamp: new Date().toISOString(),
    });
  }

  // Mutex lock
  const result = await withLock(async () => {
    return await performTurnOff(duration);
  });

  // If the lock was already held, result is the busy response
  if (result.status === 'busy') {
    return res.status(409).json(result);
  }

  const statusCode = result.success ? 200 : 500;
  res.status(statusCode).json(result);
});

// Backward-compatible alias: turn off for 2 hours (delegate naar /turn-off logica)
app.post('/turn-off-for-two-hours', async (req, res) => {
  log('info', 'POST /turn-off-for-two-hours ontvangen (verouderd, geforceerd duration=2)');

  // Cooldown check
  if (isCoolingDown()) {
    const remaining = cooldownRemaining();
    log('warning', `Aanvraag afgewezen - cooldown actief (${remaining}s resterend)`);
    return res.status(429).json({
      success: false,
      status: 'cooldown',
      error: `Cooldown actief. Probeer opnieuw over ${remaining} seconden.`,
      cooldownRemainingSeconds: remaining,
      timestamp: new Date().toISOString(),
    });
  }

  // Mutex lock
  const result = await withLock(async () => {
    return await performTurnOff(2);
  });

  // If the lock was already held, result is the busy response
  if (result.status === 'busy') {
    return res.status(409).json(result);
  }

  const statusCode = result.success ? 200 : 500;
  res.status(statusCode).json(result);
});

// Manual login trigger (used by ingress page)
app.post('/login', async (req, res) => {
  log('info', 'POST /login ontvangen');

  const username = req.body?.username || CONFIG_USERNAME;
  const password = req.body?.password || CONFIG_PASSWORD;

  if (!username || !password) {
    return res.status(400).json({
      success: false,
      status: 'missing_credentials',
      error: 'Gebruikersnaam en wachtwoord vereist. Voer deze in via de add-on configuratie of in het formulier.',
    });
  }

  const result = await withLock(async () => {
    let context = null;
    try {
      context = await launchBrowserContext();
      const page = await context.newPage();
      await page.goto(ZONNEDIMMER_URL, { waitUntil: 'networkidle', timeout: BROWSER_TIMEOUT_MS });
      await attemptLogin(page, username, password);
      return {
        success: true,
        status: 'login_success',
        message: 'Succesvol ingelogd. Sessie is persistent opgeslagen.',
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      log('error', `Login fout: ${error.message}`);
      return {
        success: false,
        status: 'login_failed',
        error: error.message,
        timestamp: new Date().toISOString(),
      };
    } finally {
      if (context) {
        try {
          await context.close();
        } catch {}
      }
    }
  });

  if (result.status === 'busy') {
    return res.status(409).json(result);
  }

  const statusCode = result.success ? 200 : 401;
  res.status(statusCode).json(result);
});

// Start server
app.listen(PORT, () => {
  log('info', `Zonnedimmer add-on service gestart op poort ${PORT}`);
  log('info', `Zonnedimmer URL: ${ZONNEDIMMER_URL}`);
  log('info', `Headless: ${HEADLESS}, Cooldown: ${COOLDOWN_MS / 60000} min`);
  log('info', `Profielmap: ${PROFILE_DIR}`);
});
