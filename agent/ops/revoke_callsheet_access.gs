/**
 * Revoke link-sharing and stale access on old call sheets.
 *
 * WHY THIS IS A SCRIPT AND NOT PART OF THE AGENT
 * The Google Drive connector the agent uses can grant access and read
 * permissions, but it has no call that removes one — `share_file` only ever
 * raises a person's role, never lowers it. So the agent can find every
 * exposed file and cannot close a single one. This script runs inside your own
 * Google account, where the full Drive API is available, and closes them.
 *
 * WHAT IT DOES
 *   1. Finds every file you own whose name contains "callsheet".
 *   2. Reports which ones are readable or editable by anyone with the link,
 *      and who else has been given access individually.
 *   3. With DRY_RUN off, sets link-sharing to private and removes the
 *      individual editors and viewers you have not exempted.
 *
 * HOW TO RUN IT
 *   1. Go to script.google.com and start a new project.
 *   2. Paste this whole file in, replacing what is there.
 *   3. Run `auditCallsheets` first. It changes nothing. Read the log
 *      (View > Logs) and check the list looks right.
 *   4. Add any address that should keep access to KEEP_ACCESS below.
 *   5. Set DRY_RUN to false and run `revokeCallsheetAccess`.
 *
 * The first run will ask you to authorise the script against your own
 * account. That is expected — it is your script, running as you.
 *
 * THIS IS NOT REVERSIBLE. Someone who loses access has to be re-shared
 * manually. Run the audit first and read it properly.
 */

// Set to false only when you have read the audit output and mean it.
var DRY_RUN = true;

// Which files to touch. Matched case-insensitively against the file name.
var NAME_CONTAINS = 'callsheet';

// Or name the exact files instead, by Drive file ID. When this list is not
// empty it REPLACES the name search entirely and only these files are touched.
//
// Use this for a day's call sheets, whose names carry the poll and the date
// rather than the word "callsheet" — and because naming the file you mean is
// safer than a name match that might sweep up something you forgot about.
//
// Wednesday 23 September 2026, the two sheets the callers were given:
var ONLY_FILE_IDS = [
  '1mqcE4A-5zcEKJ0shEpnlT3oy9PMwer5WfG9VrU5YG2U',  // Te Tai Tonga 500 - 23-09-2026
  '1Qg3Rd90rQsKBUeEFKtyJZzmZoqo2dwM3t63TcE9WgwA',  // Te Tai Hauauru 500 - 23-09-2026
];

// Addresses that keep their access. Put yourself and anyone who genuinely
// still needs these — a co-owner, an accountant, your client contact.
var KEEP_ACCESS = [
  // 'someone@example.com',
];

// Files that must be left completely alone, by Drive file ID.
var SKIP_FILE_IDS = [
  // '1NqYY08oktK8tTiUvPcLieU2No90CLZ_e-i_9tYgnsWw',
];


/** Report what is exposed. Changes nothing, ever. */
function auditCallsheets() {
  var report = scan_();
  Logger.log('=== CALL SHEET ACCESS AUDIT ===');
  Logger.log(ONLY_FILE_IDS.length
    ? 'Files named explicitly by ID: ' + report.total
    : 'Files owned by you matching "' + NAME_CONTAINS + '": ' + report.total);
  Logger.log('');

  if (report.linkShared.length) {
    Logger.log('--- OPEN TO ANYONE WITH THE LINK (%s) ---', report.linkShared.length);
    report.linkShared.forEach(function (item) {
      Logger.log('  [%s] %s', item.access, item.name);
      Logger.log('      %s', item.url);
    });
    Logger.log('');
  }

  if (report.individuals.length) {
    Logger.log('--- SHARED WITH NAMED PEOPLE (%s) ---', report.individuals.length);
    report.individuals.forEach(function (item) {
      Logger.log('  %s', item.name);
      Logger.log('      editors: %s', item.editors.join(', ') || '(none)');
      Logger.log('      viewers: %s', item.viewers.join(', ') || '(none)');
    });
    Logger.log('');
  }

  if (!report.linkShared.length && !report.individuals.length) {
    Logger.log('Nothing exposed. Every matching file is private to you.');
  }
  Logger.log('Run revokeCallsheetAccess with DRY_RUN = false to close these.');
  return report;
}


/** Close the exposures the audit found. */
function revokeCallsheetAccess() {
  var keep = {};
  KEEP_ACCESS.forEach(function (address) {
    keep[String(address).trim().toLowerCase()] = true;
  });
  var skip = {};
  SKIP_FILE_IDS.forEach(function (id) { skip[id] = true; });

  var files = targets_();

  var closed = 0, removed = 0, seen = 0, failed = 0;
  while (files.hasNext()) {
    var file = files.next();
    seen++;
    if (skip[file.getId()]) {
      Logger.log('SKIP (listed)  %s', file.getName());
      continue;
    }

    try {
      // 1. Link sharing.
      if (file.getSharingAccess() !== DriveApp.Access.PRIVATE) {
        Logger.log('%s link sharing (%s) on %s',
          DRY_RUN ? 'WOULD CLOSE' : 'CLOSED',
          String(file.getSharingAccess()), file.getName());
        if (!DRY_RUN) {
          file.setSharing(DriveApp.Access.PRIVATE, DriveApp.Permission.VIEW);
        }
        closed++;
      }

      // 2. Individually shared people.
      var owner = file.getOwner();
      var ownerEmail = owner ? owner.getEmail().toLowerCase() : '';

      file.getEditors().forEach(function (person) {
        var address = person.getEmail().toLowerCase();
        if (!address || address === ownerEmail || keep[address]) return;
        Logger.log('%s editor %s from %s',
          DRY_RUN ? 'WOULD REMOVE' : 'REMOVED', address, file.getName());
        if (!DRY_RUN) file.removeEditor(person);
        removed++;
      });

      file.getViewers().forEach(function (person) {
        var address = person.getEmail().toLowerCase();
        if (!address || address === ownerEmail || keep[address]) return;
        Logger.log('%s viewer %s from %s',
          DRY_RUN ? 'WOULD REMOVE' : 'REMOVED', address, file.getName());
        if (!DRY_RUN) file.removeViewer(person);
        removed++;
      });
    } catch (error) {
      // One file you do not fully control must not stop the other fifty-nine.
      failed++;
      Logger.log('FAILED on %s: %s', file.getName(), error.message);
    }
  }

  Logger.log('');
  Logger.log('=== %s ===', DRY_RUN ? 'DRY RUN - NOTHING CHANGED' : 'DONE');
  Logger.log('%s file(s) checked, %s link-share(s) closed, %s person-share(s) removed, %s failed',
    seen, closed, removed, failed);
  if (DRY_RUN) {
    Logger.log('Set DRY_RUN = false at the top and run again to apply this.');
  }
}


/** Gather the current state without changing anything. */
/**
 * The files both passes work on.
 *
 * Naming exact file IDs wins over the name search: it is the difference
 * between closing two sheets and closing everything that happens to be called
 * something similar. Both the audit and the revoke pass call this, so what you
 * read in the audit is exactly what gets closed.
 */
function targets_() {
  if (ONLY_FILE_IDS.length) {
    var picked = ONLY_FILE_IDS.map(function (id) { return DriveApp.getFileById(id); });
    var i = 0;
    return { hasNext: function () { return i < picked.length; },
             next: function () { return picked[i++]; } };
  }
  return DriveApp.searchFiles(
    'title contains "' + NAME_CONTAINS + '" and "me" in owners and trashed = false'
  );
}


function scan_() {
  var queue = targets_();
  var report = { total: 0, linkShared: [], individuals: [] };

  while (queue.hasNext()) {
    var file = queue.next();
    report.total++;
    try {
      var access = String(file.getSharingAccess());
      if (access !== String(DriveApp.Access.PRIVATE)) {
        report.linkShared.push({
          name: file.getName(),
          url: file.getUrl(),
          access: access + '/' + String(file.getSharingPermission()),
        });
      }

      var owner = file.getOwner();
      var ownerEmail = owner ? owner.getEmail().toLowerCase() : '';
      var editors = file.getEditors()
        .map(function (p) { return p.getEmail(); })
        .filter(function (a) { return a && a.toLowerCase() !== ownerEmail; });
      var viewers = file.getViewers()
        .map(function (p) { return p.getEmail(); })
        .filter(function (a) { return a && a.toLowerCase() !== ownerEmail; });

      if (editors.length || viewers.length) {
        report.individuals.push({
          name: file.getName(), editors: editors, viewers: viewers,
        });
      }
    } catch (error) {
      Logger.log('Could not read %s: %s', file.getName(), error.message);
    }
  }
  return report;
}
