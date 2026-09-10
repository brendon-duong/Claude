/**
 * Allocate a poll's numbers straight into your own spreadsheets.
 *
 * WHY THIS IS A SCRIPT
 * The Drive connector the agent uses can read your files and rename them, but
 * it cannot change what is inside one: its update call is metadata only. So
 * the agent can work out the allocation and hand you a finished workbook, and
 * it cannot write a single cell into the sheets you already have. This runs
 * inside your account, where it can.
 *
 * WHAT IT DOES
 *   1. Reads the number pools in the order listed.
 *   2. Gives each tab of the call sheet a contiguous block — 200 by default —
 *      writing ID into column A and Number into column B.
 *   3. Shades every row it used green, in the pool it came from.
 *   4. Renames each pool with where it got up to: "ALL USED" when a pool is
 *      finished, otherwise "USED TO <last id>".
 *
 * A caller is never given a block split across two pools. They work down the
 * list, cross into another survey's numbers, and have no way to know.
 *
 * BEFORE YOU RUN IT
 * The pools must be Google Sheets, not .xlsx. Cell shading cannot be applied
 * to an .xlsx in Drive by anything — it is a file, not a sheet. To convert:
 * open the .xlsx from Drive, then File > Save as Google Sheets. Do that once
 * per pool and paste the new IDs below. The script says so plainly if you
 * miss one.
 *
 * HOW TO RUN IT
 *   1. script.google.com, new project, paste this in.
 *   2. Fill in the IDs below. The ID is the long string in the sheet's URL,
 *      between /d/ and /edit.
 *   3. Run `preview`. It changes nothing and prints what it would do.
 *   4. Read it. Then set DRY_RUN to false and run `allocate`.
 *
 * Running `allocate` twice would hand the same numbers out again, so it
 * refuses if the call sheet already has numbers in it. Clear the tabs first
 * if you really mean to redo it.
 */

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

var DRY_RUN = true;

// The call sheet with one tab per caller. Blocks are written in tab order.
var CALLSHEET_ID = '1Rxzw_YPtyGbRuPUFdSNSg56-EEdos_V7F7rXNvgnoc8';

// The pools, drawn in this order. Google Sheet IDs, not .xlsx.
var POOL_IDS = [
  '',  // Wellington Bays Numbers September 2026  (convert to a Sheet first)
  '',  // Wellington Bays Numbers Part 2 September 2026
];

var PER_CALLER = 200;
var GREEN = '#c6efce';

// Tabs to leave alone — a notes or summary tab that is not a caller.
var SKIP_TABS = [];


// ---------------------------------------------------------------------------

function preview() {
  DRY_RUN = true;
  allocate();
}


function allocate() {
  var callsheet = SpreadsheetApp.openById(CALLSHEET_ID);
  var tabs = callsheet.getSheets().filter(function (sheet) {
    return SKIP_TABS.indexOf(sheet.getName()) === -1;
  });
  Logger.log('Call sheet: "%s", %s caller tab(s)', callsheet.getName(), tabs.length);

  if (!DRY_RUN) {
    var alreadyFilled = tabs.filter(function (tab) {
      return String(tab.getRange('A2').getValue()).trim() !== '';
    });
    if (alreadyFilled.length) {
      // Running twice would issue the same numbers to two different days.
      throw new Error(
        'The call sheet already has numbers in it (' + alreadyFilled[0].getName() +
        '). Clear the tabs first if you really mean to allocate again.');
    }
  }

  var pools = POOL_IDS.map(loadPool_).filter(function (pool) { return pool; });
  if (!pools.length) {
    throw new Error('No pools loaded. Fill in POOL_IDS at the top.');
  }

  // -- draw the blocks ------------------------------------------------------
  var plan = [];       // {tab, pool, rows}
  var pending = tabs.slice();

  for (var p = 0; p < pools.length && pending.length; p++) {
    var pool = pools[p];
    var lastPool = p === pools.length - 1;
    var cursor = 0;
    var stillPending = [];

    for (var t = 0; t < pending.length; t++) {
      var chunk = pool.rows.slice(cursor, cursor + PER_CALLER);
      // A short block means this pool ran out mid-caller. Send them to the
      // next pool for a whole one; only where there is nothing better is a
      // part-block worth having.
      if (chunk.length === PER_CALLER || (lastPool && chunk.length)) {
        plan.push({ tab: pending[t], pool: pool, rows: chunk });
        cursor += chunk.length;
      } else {
        stillPending.push(pending[t]);
      }
    }
    pending = stillPending;
  }

  // -- report ---------------------------------------------------------------
  Logger.log('');
  plan.forEach(function (item) {
    Logger.log('  %s  %s numbers  %s-%s  from %s',
      pad_(item.tab.getName(), 14), pad_(String(item.rows.length), 4),
      item.rows[0].id, item.rows[item.rows.length - 1].id, item.pool.name);
  });
  pending.forEach(function (tab) {
    Logger.log('  !! %s got nothing: the pools ran out', tab.getName());
  });

  if (DRY_RUN) {
    Logger.log('');
    Logger.log('=== DRY RUN - NOTHING CHANGED ===');
    Logger.log('Set DRY_RUN = false and run allocate to apply this.');
    return;
  }

  // -- write the call sheet -------------------------------------------------
  plan.forEach(function (item) {
    var values = item.rows.map(function (row) { return [row.id, row.phone]; });
    var range = item.tab.getRange(2, 1, values.length, 2);
    // Without this a number like 0212507803 is stored as 212507803, and the
    // caller is handed a number that cannot be rung.
    range.setNumberFormat('@');
    range.setValues(values);
  });
  Logger.log('');
  Logger.log('Wrote %s tab(s).', plan.length);

  // -- shade and rename the pools ------------------------------------------
  pools.forEach(function (pool) {
    var used = plan.filter(function (item) { return item.pool === pool; });
    if (!used.length) {
      Logger.log('%s: nothing drawn', pool.name);
      return;
    }

    var rowNumbers = [];
    used.forEach(function (item) {
      item.rows.forEach(function (row) { rowNumbers.push(row.rowNumber); });
    });
    rowNumbers.sort(function (a, b) { return a - b; });

    // Shade in runs rather than row by row: 3,400 separate calls to a sheet
    // is slow enough to time the script out.
    var width = pool.sheet.getLastColumn();
    var runStart = rowNumbers[0];
    var previous = rowNumbers[0];
    for (var i = 1; i <= rowNumbers.length; i++) {
      var current = rowNumbers[i];
      if (current !== previous + 1) {
        pool.sheet.getRange(runStart, 1, previous - runStart + 1, width)
          .setBackground(GREEN);
        runStart = current;
      }
      previous = current;
    }

    var lastId = used[used.length - 1].rows[used[used.length - 1].rows.length - 1].id;
    var drawn = rowNumbers.length;
    var remaining = pool.rows.length - drawn;
    var title = stripMark_(pool.name) +
      (remaining === 0 ? ' - ALL USED' : ' - USED TO ' + lastId);
    DriveApp.getFileById(pool.id).setName(title);

    Logger.log('%s: %s row(s) green, %s left -> renamed "%s"',
      pool.name, drawn, remaining, title);
  });

  Logger.log('');
  Logger.log('=== DONE ===');
}


// ---------------------------------------------------------------------------
// Reading a pool
// ---------------------------------------------------------------------------

// "Phone" beats "Mobile" beats "Home Phone". An electoral-roll extract carries
// all three; the plain "Phone" column is the one already consolidated to the
// best number for that person, and taking "Mobile" would silently drop
// everyone who only has a landline.
var PHONE_HEADERS = [
  ['phone number', 'phone', 'contact number', 'number'],
  ['mobile', 'cell'],
  ['home phone', 'landline'],
];
var NOT_A_PHONE = ['source', 'type', 'id', 'code', 'count'];


function loadPool_(id) {
  if (!id) return null;

  var book;
  try {
    book = SpreadsheetApp.openById(id);
  } catch (error) {
    var file = null;
    try { file = DriveApp.getFileById(id); } catch (ignored) {}
    if (file && file.getMimeType().indexOf('spreadsheetml') !== -1) {
      throw new Error(
        '"' + file.getName() + '" is an .xlsx file, not a Google Sheet, so its ' +
        'cells cannot be shaded. Open it from Drive and use ' +
        'File > Save as Google Sheets, then put the new ID in POOL_IDS.');
    }
    throw error;
  }

  var sheet = book.getSheets()[0];
  var values = sheet.getDataRange().getValues();
  if (!values.length) throw new Error('"' + book.getName() + '" is empty.');

  var phoneAt = phoneColumn_(values[0]);
  if (phoneAt === -1) {
    throw new Error('Could not find a phone column in "' + book.getName() +
      '". Headings are: ' + values[0].join(', '));
  }

  var rows = [];
  var startAfter = markFrom_(book.getName());
  for (var r = 1; r < values.length; r++) {
    var id_ = parseInt(String(values[r][0]).trim(), 10);
    if (isNaN(id_)) continue;
    if (startAfter !== null && id_ <= startAfter) continue;
    var phone = cleanNumber_(values[r][phoneAt]);
    if (!phone) continue;
    rows.push({ id: id_, phone: phone, rowNumber: r + 1 });
  }

  Logger.log('%s: %s usable number(s)%s', book.getName(), rows.length,
    startAfter !== null ? ', resuming after ' + startAfter : '');
  return { id: id, name: book.getName(), sheet: sheet, rows: rows };
}


function phoneColumn_(headers) {
  var cleaned = headers.map(function (h) { return String(h || '').trim().toLowerCase(); });
  for (var tier = 0; tier < PHONE_HEADERS.length; tier++) {
    var words = PHONE_HEADERS[tier];
    // An exact heading wins, so "Phone" is not beaten by "Home Phone Source".
    for (var i = 0; i < cleaned.length; i++) {
      if (words.indexOf(cleaned[i]) !== -1) return i;
    }
    for (var j = 0; j < cleaned.length; j++) {
      var name = cleaned[j];
      var hit = words.some(function (w) { return name.indexOf(w) !== -1; });
      var bad = NOT_A_PHONE.some(function (w) { return name.indexOf(w) !== -1; });
      if (hit && !bad) return j;
    }
  }
  return -1;
}


function cleanNumber_(value) {
  if (value === null || value === undefined) return '';
  var text = String(value).trim();
  if (!text) return '';
  if (text.slice(-2) === '.0') text = text.slice(0, -2);
  // A sheet storing 0212507803 as a number gives back 212507803.
  var digits = text.replace(/\D/g, '');
  if (digits && text.charAt(0) !== '0' && digits.length >= 8 && digits.length <= 10 &&
      (digits.charAt(0) === '2' || digits.charAt(0) === '4') &&
      text.indexOf(' ') === -1) {
    text = '0' + text;
  }
  return text;
}


// "USED TO 3400" / "USE FROM 3401" — the two forms need opposite arithmetic.
// "USED TO n" means n is spent; "USE FROM n" means n is still available.
var MARK = /\b(use\s+from|used\s+to|start\s+(?:at|from)|up\s+to)\b[^\d]{0,12}(\d+)/i;

function markFrom_(title) {
  var match = MARK.exec(title || '');
  if (!match) return null;
  var inclusive = /used\s+to|up\s+to/i.test(match[1]);
  return inclusive ? parseInt(match[2], 10) : parseInt(match[2], 10) - 1;
}

function stripMark_(title) {
  return String(title || '').replace(/\s*[-–—]?\s*(use\s+from|used\s+to|start\s+(?:at|from)|up\s+to)\b[^\d]{0,12}\d+\s*$/i, '')
    .replace(/\s*[-–—]?\s*ALL USED\s*$/i, '').trim();
}

function pad_(text, width) {
  text = String(text);
  while (text.length < width) text += ' ';
  return text;
}
