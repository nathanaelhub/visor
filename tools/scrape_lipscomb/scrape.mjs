// Read pages of Lipscomb's public 2026-27 catalog (catalog.lipscomb.edu) for spec 07, US-7.3.
//
// The site answers plain HTTP with an empty 202 and a JavaScript challenge, so a headless browser
// loads each page. It asks every crawler to wait 120 s between requests (robots.txt crawl-delay);
// this script waits that long between pages, skips anything already in the cache, and keeps raw
// pages in data/private/scrape-cache/lipscomb/ (git-ignored). Turning pages into CSV rows is done
// separately (parse.py), so a parser fix never needs another request.
//
//   node scrape.mjs name=URL [name=URL ...]
//   CHROME=/path/to/chrome node scrape.mjs ...      (otherwise the first browser found below)
//   CACHE_DIR=... node scrape.mjs ...               (tools/scrape_external uses this for challenge pages)
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const cache = process.env.CACHE_DIR || join(here, '..', '..', 'data', 'private', 'scrape-cache', 'lipscomb')
const DELAY_MS = 125_000

function browserPath() {
  if (process.env.CHROME) return process.env.CHROME
  const pw = join(homedir(), 'Library', 'Caches', 'ms-playwright')
  const fromPlaywright = existsSync(pw)
    ? readdirSync(pw).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse()
      .map((d) => join(pw, d, 'chrome-mac-arm64', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing'))
    : []
  const all = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ...fromPlaywright,
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser']
  const found = all.find((p) => existsSync(p))
  if (!found) throw new Error('No Chrome found; set CHROME=/path/to/chrome')
  return found
}

const jobs = process.argv.slice(2).map((a) => { const i = a.indexOf('='); return [a.slice(0, i), a.slice(i + 1)] })
mkdirSync(cache, { recursive: true })
const todo = jobs.filter(([name]) => !existsSync(join(cache, `${name}.html`)))
console.log(`${jobs.length - todo.length} cached, ${todo.length} to fetch`)
if (todo.length) {
  const browser = await chromium.launch({ executablePath: browserPath(), headless: true })
  const page = await browser.newPage({ userAgent: undefined })
  for (const [i, [name, url]] of todo.entries()) {
    if (i > 0) { console.log(`  waiting ${DELAY_MS / 1000}s (crawl-delay)`); await new Promise((r) => setTimeout(r, DELAY_MS)) }
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    // The challenge reloads the page once it passes; wait for the catalog's own markup.
    await page.waitForSelector('#acalog-content, .block_content, td.block_content', { timeout: 120_000 })
    writeFileSync(join(cache, `${name}.html`), await page.content())
    console.log(`  fetched ${name} ${url}`)
  }
  await browser.close()
}
console.log('done')
