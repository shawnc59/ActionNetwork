// function saveToken() {
//   const token = "...";
//   console.log("About to save token ...");
//   PropertiesService.getScriptProperties().setProperty('AN_API_TOKEN', token);
//   console.log("Token saved securely!");
// }

////////////////////////////////////////////////////////////////////////////////
// Log the user, timestamp, and result to a 'Change Log' sheet.
function logActivity({status, action = "Update Email Stats", runningAsTrigger = false}) {
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
    "<Google account Email>"
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
    .addItem('Update Email Statistics', 'getActionNetworkStats')
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
////////////////////////////////////////////////////////////////////////////////
// Main function to get the Email stats from Action Network
////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////
function getActionNetworkStats(e) {
  // Helper functions
  function calcPct(dividend, divisor) {
    if (divisor === 0) { return 0; } // Avoid division by zero
    return dividend / divisor;
  }

  // Helper function to check if an object is empty (no enumerable properties).
  function isEmptyObject(obj) {
    // Check if obj is a non-null, non-array object
    return (
      obj !== null && // Exclude null
      typeof obj === 'object' && // Ensure it's an object
      !Array.isArray(obj) && // Exclude arrays
      Object.keys(obj).length === 0 // Check for no enumerable properties
    );
  }

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
  const anApiToken = PropertiesService.getScriptProperties().getProperty('AN_API_TOKEN');
  if (!anApiToken) {
    if (!runningAsTrigger) { SpreadsheetApp.getUi().alert("API Token missing."); }
    logActivity({status: "Error: API Token missing.", runningAsTrigger: runningAsTrigger});
    return;
  }
  // Some housework
  // If a sheet named "Email Stats" doesn't exist then create it.
  const googleSheet = SpreadsheetApp.getActiveSpreadsheet();
  const reportSheet = googleSheet.getSheetByName("Email Stats") || googleSheet.insertSheet("Email Stats");
  // AN API authorization is by the token passed as a header.
  const headers = { "OSDI-API-Token": anApiToken };
  const API_BASE_URI = "https://actionnetwork.org/api/v2";
  
  let uri = "/messages";
  let moreData = true;
  let messageStats = [];
  // Call the /messages API endpoint and keep looping until all have been returned.
  try {
    while (moreData) {
      const url = `${API_BASE_URI}${uri}`;
      const response = UrlFetchApp.fetch(url, { "headers": headers });
      const data = JSON.parse(response.getContentText());
      const messages = data['_embedded']['osdi:messages'];

      messages.forEach(message => {
        if (message.status === 'sent') {
          const stats = message.statistics || {};
          if (isEmptyObject(stats)) {
            logActivity({status: "Warning: No stats found for message '" + message.subject + "'", runningAsTrigger: runningAsTrigger});
          } else {
            let totalOpened = (stats.verified_opens || 0) + (stats.machine_opened || 0);
            messageStats.push([
              calcPct(totalOpened, message.total_targeted),
              calcPct(stats.verified_opens || 0, message.total_targeted),
              calcPct(stats.clicked || 0, message.total_targeted),
              calcPct(stats.actions || 0, message.total_targeted),
              message.subject,
              message.from,
              message.reply_to,
              new Date(message.sent_start_date),
              message.total_targeted || 0,
              totalOpened,
              stats.verified_opens || 0,
              stats.machine_opened || 0,
              stats.clicked || 0,
              stats.actions || 0,
              stats.unsubscribed || 0,
              stats.bounced || 0,
              stats.spam_reports || 0
            ]);
          }
        } // if (message.status === 'sent')
      });
      // If the current page is the same (or greater?) than total pages, then we're done. 
      // Else, increment the page index on the API endpoint for the next call.
      if (data.page >= data.total_pages) { moreData = false; } 
      else { uri = `/messages?page=${data.page + 1}`; }
    }

    // 3. Write Data to Sheet
    if (messageStats.length > 0) {
      // Sort stats records by Sent Date (4th element in the inner array) descending
      messageStats.sort((a, b) => b[3] - a[3])
      // Clear the existing contents of the target sheet, add the header, and dump the stats array to it.
      reportSheet.clear();
      reportSheet.setFrozenRows(1); // Freeze the header row
      reportSheet.getRange('A:D').setNumberFormat('0%'); // Format the percentage columns
      const headerRow = ["% Opened\n(Total)", "% Opened\n(Verified)", "% Clicked\nLink", "% Took\nAction","Subject", "From", "Reply To", "Sent Date", "Targets", "Total\nOpens", "Verified\nOpens", "Machine\nOpens", "Clicks", "Actions\nTaken", "Unsubscribed", "Bounced", "Spam\nReported"];
      reportSheet.getRange(1, 1, 1, headerRow.length).setValues([headerRow]).setFontWeight("bold").setBackground("#EFEFEF").setHorizontalAlignment("center");
      reportSheet.getRange(2, 1, messageStats.length, messageStats[0].length).setValues(messageStats);
      // Add an information timestamp
      const timestamp = "Last Updated: " + Utilities.formatDate(new Date(), "GMT-5", "yyyy-MM-dd HH:mm:ss");
      reportSheet.autoResizeColumns(1, 16);
      reportSheet.getRange("A" + (messageStats.length + 3)).setValue(timestamp).setFontStyle("italic");
//      const range = reportSheet.getRange('A2:A');
      // Set conditional formatting rule to highlight rows where % Opened (Total) is greater than 50%
      const rule = SpreadsheetApp.newConditionalFormatRule()
        .whenNumberGreaterThan(0.5)
        .setBackground('lime')
        .setRanges([reportSheet.getRange('A2:A')])
        .build();
      const rules = reportSheet.getConditionalFormatRules();
      rules.push(rule);
      reportSheet.setConditionalFormatRules(rules);
      // Sort the sheet by Sent Date (column H) in descending order
      reportSheet.sort(8, false);
      
      // 4. Log Success
      logActivity({status: "Success: " + messageStats.length + " rows updated", runningAsTrigger: runningAsTrigger});
    }
  } catch (e) {
    logActivity({status: "Error: " + e.toString(), runningAsTrigger: runningAsTrigger});
    if (!runningAsTrigger) { SpreadsheetApp.getUi().alert("An error occurred. Check the Change Log."); }
  }
}
