// function saveToken() {
//   const token = "...";
//   console.log("About to save token ...");
//   PropertiesService.getScriptProperties().setProperty('AN_API_TOKEN', token);
//   console.log("Token saved securely!");
// }

////////////////////////////////////////////////////////////////////////////////
// Log the user, timestamp, and result to a 'Change Log' sheet.
function logActivity({status, action = "Update Activist report", runningAsTrigger = false}) {
  const googleSheet = SpreadsheetApp.getActiveSpreadsheet();
  let logSheet = googleSheet.getSheetByName("Change Log");
  
  // Create the log sheet if it doesn't exist
  if (!logSheet) {
    logSheet = googleSheet.insertSheet("Change Log");
    logSheet.appendRow(["Timestamp", "User", "Action", "Status"]);
    logSheet.getRange("1:1").setFontWeight("bold").setBackground("#eeeeee");
    // Hide the log sheet so viewers don't see the sausage being made.
    // logSheet.hideSheet(); 
  }
  let user
  if (runningAsTrigger) { user = "Timer trigger" }
  else { user = Session.getActiveUser().getEmail() || "Unknown User"; }
  const timestamp = new Date();
  
  logSheet.appendRow([timestamp, user, action, status]);
}

////////////////////////////////////////////////////////////////////////////////
// Check if the current user is on the approved list to run this.
function checkUserAccess() {
  const currentUser = Session.getActiveUser().getEmail();
  
  // List of authorized email addresses (comma-separated)
  const authorizedUsers = [
    "shawn.chapla@gmail.com"
  ];

  if (authorizedUsers.indexOf(currentUser) === -1) {
    SpreadsheetApp.getUi().alert("Access Denied: " + currentUser + " is not authorized to run this update.");
    return false;
  }
  return true;
}

////////////////////////////////////////////////////////////////////////////////
// Automatically create a custom menu when the sheet is opened.
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  
  ui.createMenu('Action Network')
    .addItem('Update Activist Report', 'getActionNetworkStats')
    .addSeparator()
    .addItem('Config: Set/clear API Token', 'showTokenPrompt')
    .addToUi();
}

////////////////////////////////////////////////////////////////////////////////
// Prompt for the Action Network tokwn and save it as a script property.
function showTokenPrompt() {
  const ui = SpreadsheetApp.getUi();
  const result = ui.prompt(
    'API Token Setup',
    'Enter Action Network API token (leave blank to clear):',
    ui.ButtonSet.OK_CANCEL
  );

  if (result.getSelectedButton() == ui.Button.OK) {
    const token = result.getResponseText();
    if (token) {
      PropertiesService.getScriptProperties().setProperty('AN_API_TOKEN', token);
      action = 'Token saved securely.';
    } else {
      PropertiesService.getScriptProperties().setProperty('AN_API_TOKEN', "");
      action = 'Token value cleared.';
    }
    ui.alert('Success: ' + action);
    logActivity({status: 'Success', action: action});
  }
}

////////////////////////////////////////////////////////////////////////////////
// Main function to get the Email stats from Action Network
function getActionNetworkStats(e) {
  // Determine if this code is running interactively or as a timer trigger
  const runningAsTrigger = e && (e.triggerSource || e.authMode) ? true : false;

  // 1. Security Check if being run interactively
  if (!runningAsTrigger) {
    if (!checkUserAccess()) {
      logActivity({status: "Denied: Unauthorized User", runningAsTrigger: runningAsTrigger});
      return;
    }
  }

  // 2. Get the data from AN
  // Get the AN API token from the script properties.
  const googleSheet = SpreadsheetApp.getActiveSpreadsheet();
  const anApiToken = PropertiesService.getScriptProperties().getProperty('AN_API_TOKEN');

  if (!anApiToken) {
    if (!runningAsTrigger) { SpreadsheetApp.getUi().alert("API Token missing."); }
    logActivity({status: "Error: API Token missing.", runningAsTrigger: runningAsTrigger});
    return;
  }
  // If a sheet named "Activists" doesn't exist then create it.
  const reportSheet = googleSheet.getSheetByName("Activists") || googleSheet.insertSheet("Activists");
  // AN API authorization is by the token passed as a header.
  const headers = { "OSDI-API-Token": anApiToken };
  const API_BASE_URI = "https://actionnetwork.org/api/v2";

  // First we need to get all the tags for this group to avoid per-activist API calls later.
  let uri = "/tags"
  let moreData = true;
  let tags = {};
  
  while (moreData) {
    const url = `${API_BASE_URI}${uri}`;
    const response = UrlFetchApp.fetch(url, { "headers": headers });
    try {
      const data = JSON.parse(response.getContentText());
    } catch (e) {
      logActivity({status: "Error: " + e.toString(), runningAsTrigger: runningAsTrigger});
      if (!runningAsTrigger) { SpreadsheetApp.getUi().alert("An error occurred. Check the Change Log."); }
    }
    if (data.['_embedded'] && data.['_embedded']['osdi:tags']) {
      for (const tag of data.['_embedded']['osdi:tags']) {
        // tagID = tag["identifiers"][0].replace("action_network:", "");
        // tagName = tag["name"];
        tags[tag["identifiers"][0].replace("action_network:", "")] = tag["name"];
      }
    }
  }

  // Call the /people API endpoint and keep looping until all have been returned.
  uri = "/people";
  moreData = true;
  let activists = [];
  while (moreData) {
    const url = `${API_BASE_URI}${uri}`;
  try {
      const response = UrlFetchApp.fetch(url, { "headers": headers });
    } catch (e) {
      logActivity({status: "Error: " + e.toString(), runningAsTrigger: runningAsTrigger});
      if (!runningAsTrigger) { SpreadsheetApp.getUi().alert("An error occurred. Check the Change Log."); }
    }
    const data = JSON.parse(response.getContentText());
    const messages = data['_embedded']['osdi:messages'];

    messages.forEach(message => {
      if (message.status === 'sent') {
        const stats = message.statistics || {};
        activists.push([
          message.subject,
          message.from,
          message.reply_to,
          new Date(message.sent_start_date),
          message.total_targeted || 0,
          (stats.verified_opens || 0) + (stats.machine_opened || 0),
          stats.verified_opens || 0,
          stats.machine_opened || 0,
          stats.clicked || 0,
          stats.actions || 0,
          stats.unsubscribed || 0,
          stats.bounced || 0,
          stats.spam_reports || 0
        ]);
      }
    });
    // If the current page is the same (or greater?) than total pages, then we're done. 
    // Else, increment the page index on the API endpoint for the next call.
    if (data.page >= data.total_pages) { moreData = false; } 
    else { uri = `/messages?page=${data.page + 1}`; }
  }

  // 3. Write Data to Sheet
  if (activists.length > 0) {
    // Sort stats records by Sent Date (4th element in the inner array) descending
    activists.sort((a, b) => b[3] - a[3])
    // Clear the existing contents of the target sheet, add the header, and dump the stats array to it.
    reportSheet.clear();
    const headerRow = ["Subject", "From", "Reply To", "Sent Date", "Targets", "Total Opens", "Verified", "Machine", "Clicks", "Actions Taken", "Unsubscribes", "Bounced", "Spam Reported"];
    reportSheet.getRange(1, 1, 1, headerRow.length).setValues([headerRow]).setFontWeight("bold").setBackground("#EFEFEF");
    reportSheet.getRange(2, 1, activists.length, activists[0].length).setValues(activists);
    // Add an information timestamp
    const timestamp = "Last Updated: " + Utilities.formatDate(new Date(), "GMT-5", "yyyy-MM-dd HH:mm:ss");
    reportSheet.getRange("A" + (activists.length + 3)).setValue(timestamp).setFontStyle("italic");
    reportSheet.autoResizeColumns(1, 13);
    
    // 4. Log Success
    logActivity({status: "Success: " + activists.length + " rows updated", runningAsTrigger: runningAsTrigger});
  }
}
