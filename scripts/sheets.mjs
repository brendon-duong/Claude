#!/usr/bin/env node
// Read and write Google Sheets with a service account.
//
// Credentials live in .env.local at the project root (never committed):
//   GOOGLE_SERVICE_ACCOUNT_EMAIL=sheets-bot@<project>.iam.gserviceaccount.com
//   GOOGLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
//
// A sheet is only reachable once it has been shared with that address.
//
//   node scripts/sheets.mjs inspect <sheet>
//   node scripts/sheets.mjs read    <sheet> [range] [--limit N] [--json]
//   node scripts/sheets.mjs write   <sheet> <range> '[["a","b"],["c","d"]]'
//   node scripts/sheets.mjs write   <sheet> @payload.json      (whole workbook)
//   node scripts/sheets.mjs append  <sheet> <range> '[["a","b"]]'
//   node scripts/sheets.mjs clear   <sheet> <range>
//
// <sheet> is a spreadsheet ID or the full https://docs.google.com/... URL.

import { readFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

// --- credentials -----------------------------------------------------------

function loadEnvLocal() {
  const path = resolve(ROOT, '.env.local');
  if (!existsSync(path)) return;
  for (const raw of readFileSync(path, 'utf8').split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = val;
  }
}

function credentials() {
  loadEnvLocal();
  const email = process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL;
  let key = process.env.GOOGLE_PRIVATE_KEY;
  if (!email || !key) {
    die(
      'No credentials found.\n' +
      'Expected a file at ' + resolve(ROOT, '.env.local') + ' containing:\n' +
      '  GOOGLE_SERVICE_ACCOUNT_EMAIL=sheets-bot@<project>.iam.gserviceaccount.com\n' +
      '  GOOGLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"'
    );
  }
  // A key pasted as one line carries literal backslash-n; turn those into real newlines.
  key = key.replace(/\\n/g, '\n');
  if (!key.includes('BEGIN PRIVATE KEY')) {
    die('GOOGLE_PRIVATE_KEY does not look like a private key. It must include the\n' +
        '-----BEGIN PRIVATE KEY----- line, with \\n between each line.');
  }
  return { email, key };
}

async function api() {
  const { email, key } = credentials();
  const auth = new google.auth.JWT({
    email,
    key,
    scopes: [
      'https://www.googleapis.com/auth/spreadsheets',
      'https://www.googleapis.com/auth/drive.readonly',
    ],
  });
  return { sheets: google.sheets({ version: 'v4', auth }), email };
}

// --- helpers ---------------------------------------------------------------

function die(msg) {
  console.error('\n' + msg + '\n');
  process.exit(1);
}

function sheetId(input) {
  if (!input) die('Give me a spreadsheet ID or URL.');
  const m = String(input).match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
  return m ? m[1] : String(input).trim();
}

function explain(err, email) {
  const status = err?.code ?? err?.response?.status;
  const detail = err?.errors?.[0]?.message ?? err?.response?.data?.error?.message ?? err?.message;
  if (status === 403 && /caller does not have permission|permission/i.test(detail || '')) {
    return 'Google says: permission denied.\n' +
           'The sheet has not been shared with ' + email + '.\n' +
           'Open the sheet, click Share, paste that address, set it to Editor, Send.';
  }
  if (status === 404) {
    return 'Google says: not found.\n' +
           'Either the spreadsheet ID is wrong, or the file has not been shared with ' + email + '.';
  }
  if (status === 400 && /Unable to parse range/i.test(detail || '')) {
    return 'Google could not understand the range.\n' +
           "Use a tab name, optionally with cells: 'Sheet1' or 'Sheet1!A1:D20'.\n" +
           'A tab name containing spaces needs quotes round it inside the range.';
  }
  if (/invalid_grant|Invalid JWT/i.test(detail || '')) {
    return 'Google rejected the key itself.\n' +
           'The private key in .env.local is probably truncated or its \\n line breaks were lost.';
  }
  return 'Google returned an error' + (status ? ' (' + status + ')' : '') + ':\n' + (detail || String(err));
}

function table(rows) {
  if (!rows.length) return '(no rows)';
  const width = Math.max(...rows.map(r => r.length));
  const grid = rows.map(r => Array.from({ length: width }, (_, i) => String(r[i] ?? '')));
  const w = Array.from({ length: width }, (_, i) =>
    Math.min(40, Math.max(...grid.map(r => r[i].length))));
  return grid.map(r =>
    r.map((c, i) => (c.length > w[i] ? c.slice(0, w[i] - 1) + '…' : c).padEnd(w[i])).join('  ')
  ).join('\n');
}

function parseRows(arg) {
  if (!arg) die('Give me the rows to write, as JSON: \'[["a","b"],["c","d"]]\'');
  let rows;
  try {
    rows = JSON.parse(arg);
  } catch {
    die('Could not read those rows as JSON. Expected something like:\n  \'[["Name","Total"],["Kharen",12]]\'');
  }
  if (!Array.isArray(rows)) die('Rows must be a JSON array.');
  if (rows.length && !Array.isArray(rows[0])) rows = [rows]; // a single row is fine
  return rows;
}

// --- commands --------------------------------------------------------------

async function cmdInspect(id) {
  const { sheets, email } = await api();
  const res = await sheets.spreadsheets.get({ spreadsheetId: id, includeGridData: false });
  const d = res.data;
  console.log('\n' + d.properties.title);
  console.log('https://docs.google.com/spreadsheets/d/' + id);
  console.log('read as ' + email + '\n');
  for (const s of d.sheets) {
    const p = s.properties;
    console.log(
      '  ' + p.title.padEnd(32) +
      String(p.gridProperties?.rowCount ?? '?').padStart(8) + ' rows' +
      String(p.gridProperties?.columnCount ?? '?').padStart(6) + ' cols'
    );
  }
  console.log('');
}

async function cmdRead(id, range, opts) {
  const { sheets } = await api();
  let target = range;
  if (!target) {
    const meta = await sheets.spreadsheets.get({ spreadsheetId: id, includeGridData: false });
    target = meta.data.sheets[0].properties.title;
  }
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: id,
    range: target,
    valueRenderOption: 'UNFORMATTED_VALUE',
    dateTimeRenderOption: 'FORMATTED_STRING',
  });
  let rows = res.data.values ?? [];
  if (opts.limit) rows = rows.slice(0, opts.limit);
  if (opts.json) console.log(JSON.stringify(rows, null, 2));
  else {
    console.log('\n' + (res.data.range || target) + '  —  ' + rows.length + ' row(s)\n');
    console.log(table(rows));
    console.log('');
  }
}

// A payload file lets a whole workbook go up in one call, instead of the rows
// being retyped as a JSON argument. Hand-copying tens of thousands of cells is
// how a call sheet picks up a silent transcription error, so the rows are read
// from disk and never pass through an argument.
//
//   node scripts/sheets.mjs write <sheet> @/path/payload.json
//   payload: {"tabs": {"Tab name": [[row], [row]], ...}}
//
// Tabs named in the payload that do not exist yet are created. A brand-new
// spreadsheet arrives with one empty default tab; that one is renamed to the
// first tab in the payload rather than left behind as a stray.
async function cmdWriteBook(id, payloadPath) {
  const path = payloadPath.slice(1);
  if (!existsSync(path)) die('No payload file at ' + path);
  let payload;
  try {
    payload = JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    die('Could not read ' + path + ' as JSON.');
  }
  const tabs = payload.tabs ?? {};
  if (typeof tabs !== 'object') die('Payload "tabs" must be an object: {"tabs": {"Name": [[...]]}}');

  const { sheets } = await api();
  const meta = await sheets.spreadsheets.get({ spreadsheetId: id, includeGridData: false });
  const existing = meta.data.sheets.map(s => s.properties);
  const wanted = Object.keys(tabs);

  const requests = [];
  const have = new Set(existing.map(p => p.title));
  // The lone untouched default tab becomes the first one we want, so a new
  // spreadsheet does not keep an empty "Sheet1" beside the real tabs.
  if (wanted.length && existing.length === 1 && !have.has(wanted[0]) && /^Sheet1$/i.test(existing[0].title)) {
    requests.push({ updateSheetProperties: {
      properties: { sheetId: existing[0].sheetId, title: wanted[0] }, fields: 'title' } });
    have.delete(existing[0].title);
    have.add(wanted[0]);
  }
  // A caller dropping out is a rename, not a rebuild: the tab keeps its number
  // block and changes whose name is on it, so nobody's numbers move.
  for (const r of payload.rename ?? []) {
    const from = existing.find(p => p.title === r.from);
    if (!from) die('No tab named ' + r.from + ' to rename.');
    requests.push({ updateSheetProperties: {
      properties: { sheetId: from.sheetId, title: r.to }, fields: 'title' } });
    have.delete(r.from); have.add(r.to);
  }
  for (const title of wanted) {
    if (!have.has(title)) { requests.push({ addSheet: { properties: { title } } }); have.add(title); }
  }
  if (requests.length) {
    await sheets.spreadsheets.batchUpdate({ spreadsheetId: id, requestBody: { requests } });
    console.log('tabs prepared: ' + requests.length);
  }

  // Background colour is the one thing a values write cannot carry, and it is
  // how both Curia and Pacific Link mark a number as spent. A payload may name
  // row bands to fill: {"shade": [{tab, firstRow, lastRow, color: [r,g,b]}]},
  // where firstRow/lastRow are 1-based sheet rows.
  async function shade(bands) {
    const fresh = await sheets.spreadsheets.get({ spreadsheetId: id, includeGridData: false });
    const byTitle = new Map(fresh.data.sheets.map(s => [s.properties.title, s.properties.sheetId]));
    const reqs = [];
    for (const b of bands) {
      const sid = byTitle.get(b.tab);
      if (sid === undefined) die('No tab named ' + b.tab + ' to shade.');
      const [r, g, bl] = b.color;
      reqs.push({ repeatCell: {
        range: { sheetId: sid, startRowIndex: b.firstRow - 1, endRowIndex: b.lastRow,
                 startColumnIndex: 0, endColumnIndex: b.columns ?? 2 },
        cell: { userEnteredFormat: { backgroundColor: { red: r/255, green: g/255, blue: bl/255 } } },
        fields: 'userEnteredFormat.backgroundColor' } });
    }
    // One band can span tens of thousands of rows; Google takes them in batches.
    for (let i = 0; i < reqs.length; i += 20) {
      await sheets.spreadsheets.batchUpdate({
        spreadsheetId: id, requestBody: { requests: reqs.slice(i, i + 20) } });
    }
    console.log('shaded ' + bands.length + ' band(s)');
  }

  let cells = 0;
  for (const [title, rows] of Object.entries(tabs)) {
    const res = await sheets.spreadsheets.values.update({
      spreadsheetId: id,
      range: "'" + title.replace(/'/g, "''") + "'!A1",
      valueInputOption: 'USER_ENTERED',
      requestBody: { values: rows },
    });
    cells += res.data.updatedCells;
    console.log('  ' + title.padEnd(26) + String(res.data.updatedCells).padStart(7) + ' cells');
  }
  console.log('wrote ' + cells + ' cell(s) across ' + wanted.length + ' tab(s)');
  if (Array.isArray(payload.shade) && payload.shade.length) await shade(payload.shade);
}

async function cmdWrite(id, range, rowsArg) {
  if (!range) die('Give me a range to write to, e.g. \'Sheet1!A1\'');
  if (range.startsWith('@')) return cmdWriteBook(id, range);
  const rows = parseRows(rowsArg);
  const { sheets } = await api();
  const res = await sheets.spreadsheets.values.update({
    spreadsheetId: id,
    range,
    valueInputOption: 'USER_ENTERED',
    requestBody: { values: rows },
  });
  console.log('wrote ' + res.data.updatedCells + ' cell(s) to ' + res.data.updatedRange);
}

async function cmdAppend(id, range, rowsArg) {
  if (!range) die('Give me a range or tab name to append to, e.g. \'Sheet1\'');
  const rows = parseRows(rowsArg);
  const { sheets } = await api();
  const res = await sheets.spreadsheets.values.append({
    spreadsheetId: id,
    range,
    valueInputOption: 'USER_ENTERED',
    insertDataOption: 'INSERT_ROWS',
    requestBody: { values: rows },
  });
  const u = res.data.updates;
  console.log('appended ' + u.updatedRows + ' row(s) at ' + u.updatedRange);
}

async function cmdClear(id, range) {
  if (!range) die('Give me a range to clear, e.g. \'Sheet1!A2:Z999\'');
  const { sheets } = await api();
  const res = await sheets.spreadsheets.values.clear({ spreadsheetId: id, range });
  console.log('cleared ' + res.data.clearedRange);
}

// --- entry point -----------------------------------------------------------

const USAGE = `
sheets.mjs — read and write Google Sheets as the sheets-bot service account

  node scripts/sheets.mjs inspect <sheet>
      list every tab in the spreadsheet, with its size

  node scripts/sheets.mjs read <sheet> [range] [--limit N] [--json]
      print cells. No range means the first tab.

  node scripts/sheets.mjs write <sheet> <range> '[["a","b"],["c","d"]]'
      overwrite cells starting at the range's top-left corner

  node scripts/sheets.mjs append <sheet> <range> '[["a","b"]]'
      add rows underneath whatever is already there

  node scripts/sheets.mjs clear <sheet> <range>
      empty the cells, leaving the rows in place

<sheet> is a spreadsheet ID or its full https://docs.google.com/... URL.
The sheet must be shared with the service account first.
`;

async function main() {
  const argv = process.argv.slice(2);
  const opts = { json: argv.includes('--json'), limit: 0 };
  const li = argv.indexOf('--limit');
  if (li !== -1) opts.limit = parseInt(argv[li + 1], 10) || 0;
  const pos = argv.filter((a, i) =>
    !a.startsWith('--') && !(li !== -1 && i === li + 1));

  const [cmd, sheet, a, b] = pos;
  if (!cmd || cmd === 'help' || cmd === '--help') { console.log(USAGE); return; }

  const id = sheetId(sheet);
  let email = '(the service account)';
  try {
    email = credentials().email;
    switch (cmd) {
      case 'inspect': await cmdInspect(id); break;
      case 'read':    await cmdRead(id, a, opts); break;
      case 'write':   await cmdWrite(id, a, b); break;
      case 'append':  await cmdAppend(id, a, b); break;
      case 'clear':   await cmdClear(id, a); break;
      default: die('Unknown command "' + cmd + '".' + USAGE);
    }
  } catch (err) {
    die(explain(err, email));
  }
}

main();
