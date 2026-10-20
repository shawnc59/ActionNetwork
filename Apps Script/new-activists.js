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
    .addItem('Get New Joiners', 'getNewJoiners')
    .addSeparator()
    .addItem('Set number of days to look back (default: 10)', 'showLookbackPrompt')
    .addSeparator()
    .addItem('Config: Set/clear API Token', 'showTokenPrompt')
    .addToUi();
}

////////////////////////////////////////////////////////////////////////////////
// Prompt for the Action Network token and save it as a script property.
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

// Prompt for the number of days to look back and save it as a script property.
function showLookbackPrompt() {
  const ui = SpreadsheetApp.getUi();
  const result = ui.prompt(
    'Set Days to Look Back',
    'Enter the number of days to look back for new joiners (default: 10):',
    ui.ButtonSet.OK_CANCEL
  );

  if (result.getSelectedButton() == ui.Button.OK) {
    const days = parseInt(result.getResponseText());
    if (!isNaN(days)) {
      PropertiesService.getScriptProperties().setProperty('DAYS_TO_LOOK_BACK', days);
      ui.alert('Success: Number of days updated.');
    } else {
      ui.alert('Error: Please enter a valid number.');
    }
  }
}

////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////
// Main function to get activist info from Action Network
////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////
function getNewJoiners(e) {
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

  // Some prep work
  // Calculate the people API filter date based on the number of days to look back
  const daysToLookBack = parseInt(PropertiesService.getScriptProperties().getProperty('DAYS_TO_LOOK_BACK')) || 10;
  let dateLookbackDaysAgo = new Date();
  dateLookbackDaysAgo.setDate(dateLookbackDaysAgo.getDate() - daysToLookBack);
  const dateForFilter = dateLookbackDaysAgo.toISOString().split('T')[0]; // Format as YYYY-MM-DD

  // Get the AN API token from the script properties. API authorization is by the token passed as a header.
  const anApiToken = PropertiesService.getScriptProperties().getProperty('AN_API_TOKEN');
  if (!anApiToken) {
    if (!runningAsTrigger) { SpreadsheetApp.getUi().alert("API Token missing."); }
    logActivity({status: "Error: API Token missing.", runningAsTrigger: runningAsTrigger});
    return;
  }
  const headers = { "OSDI-API-Token": anApiToken };

  // If a sheet named "New joiners" doesn't exist then create it.
  const googleSheet = SpreadsheetApp.getActiveSpreadsheet();
  const reportSheet = googleSheet.getSheetByName("New joiners") || googleSheet.insertSheet("New joiners");
  const API_BASE_URI = "https://actionnetwork.org/api/v2";
  
  // Get the data from AN.
  let uri = "/people?filter=created_date%20gt%20%27" + dateForFilter + "%27";
  let moreData = true;
  let peopleData = [];
  // Call the /people API endpoint and keep looping until all have been returned.
  try {
    while (moreData) {
      const url = `${API_BASE_URI}${uri}`;
      const response = UrlFetchApp.fetch(url, { "headers": headers });
      const data = JSON.parse(response.getContentText());
      const people = data['_embedded']['osdi:people'];

      for (var person of people) {
        // Make sure the person is still subscribed to the list before adding them to the sheet. 
        if (person.email_addresses && person.email_addresses.length > 0) {
          if (person.email_addresses[0].status !== 'subscribed') {
            break; // Skip this person if not subscribed
          }
        }
        phone_number = person.phone_numbers && 
                       person.phone_numbers.length > 0 &&
                       person.phone_numbers[0].number ? person.phone_numbers[0].number : "";
        let createdDate = person.created_date ? new Date(person.created_date).toISOString().split('T')[0] : "";
        if (person.addresses && person.addresses.length > 0) {
          city = person.addresses[0].locality || "";
          state = person.addresses[0].region || "";
          zip = person.addresses[0].postal_code || "";
        }
        peopleData.push([
          createdDate,
          person.email_addresses[0].address,
          person.given_name || "",
          person.family_name || "",
          phone_number,
          city,
          state,
          zip
        ]);
      };
      // If the current page is the same (or greater?) than total pages, then we're done. 
      // Else, increment the page index on the API endpoint for the next call.
      if (data.page >= data.total_pages) { moreData = false; } 
      else { uri = uri + `&page=${data.page + 1}`; }
    }

    // Write Data to Sheet
    if (peopleData.length > 0) {
      // Clear the existing contents of the target sheet, add the header, and dump the stats array to it.
      reportSheet.clear();
      reportSheet.setFrozenRows(1); // Freeze the header row
      const headerRow = ["Created", "First Name", "Last Name", "Email", "Phone", "City", "State", "Zip"];
      reportSheet.getRange(1, 1, 1, headerRow.length).setValues([headerRow]).setFontWeight("bold").setBackground("#EFEFEF").setHorizontalAlignment("center");
      reportSheet.getRange(2, 1, peopleData.length, peopleData[0].length).setValues(peopleData);
      // Add an information timestamp
      const timestamp = "Last Updated: " + Utilities.formatDate(new Date(), "GMT-5", "yyyy-MM-dd HH:mm:ss");
      reportSheet.autoResizeColumns(1, 8);
      reportSheet.getRange("A" + (peopleData.length + 3)).setValue(timestamp).setFontStyle("italic");
      // Sort the sheet by Created Date (column A) in ascending order
      reportSheet.sort(1, true);
      
      // 4. Log Success
      logActivity({status: "Success: " + peopleData.length + " rows updated", runningAsTrigger: runningAsTrigger});
    }
  } catch (e) {
    logActivity({status: "Error: " + e.toString(), runningAsTrigger: runningAsTrigger});
    if (!runningAsTrigger) { SpreadsheetApp.getUi().alert("An error occurred. Check the Change Log."); }
  }
}
