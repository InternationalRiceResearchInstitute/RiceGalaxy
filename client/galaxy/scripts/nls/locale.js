/** en/main localization hash - for use with requirejs' i18n plugin */
define({
    root : {
// ----------------------------------------------------------------------------- masthead
"Analyze Data":
    false,
"Workflow":
    false,
"Shared Data":
    false,
"Data Libraries":
    false,
"Histories":
    false,
"Workflows":
    false,
"Visualizations":
    false,
"Pages":
    false,
"Visualization":
    false,
"New Track Browser":
    false,
"Saved Visualizations":
    false,
"Interactive Environments":
    false,
"Admin":
    false,
"Help":
    false,
"Support":
    false,
"Search":
    false,
"Mailing Lists":
    false,
"Videos":
    false,
"Wiki":
    false,
"How to Cite Galaxy":
    false,
"Interactive Tours":
    false,
"User":
    false,
"Login":
    false,
"Register":
    false,
"Login or Register":
    false,
"Logged in as":
    false,
"Preferences":
    false,
"Custom Builds":
    false,
"Logout":
    false,
"Saved Histories":
    false,
"Saved Datasets":
    false,
"Saved Pages":
    false,

//Tooltip
"Account and saved data" :
   false,
"Account registration or login" :
   false,
"Support, contact, and community" :
   false,
"Administer this Galaxy" :
   false,
"Visualize datasets" :
   false,
"Access published resources" :
   false,
"Chain tools into workflows" :
   false,
"Analysis home view" :
   false,

// ---------------------------------------------------------------------------- histories
// ---- history/options-menu
"History Lists":
    false,
// Saved histories is defined above.
// "Saved Histories":
//     false,
"Histories Shared with Me":
    false,
"Current History":
    false,
"Create New":
    false,
"Copy History":
    false,
"Share or Publish":
    false,
"Show Structure":
    false,
"Extract Workflow":
    false,
// Delete is defined elsewhere, but is also in this menu.
// "Delete":
//     false,
"Delete Permanently":
    false,
"Dataset Actions":
    false,
"Copy Datasets":
    false,
"Dataset Security":
    false,
"Resume Paused Jobs":
    false,
"Collapse Expanded Datasets":
    false,
"Unhide Hidden Datasets":
    false,
"Delete Hidden Datasets":
    false,
"Purge Deleted Datasets":
    false,
"Downloads":
    false,
"Export Tool Citations":
    false,
"Export History to File":
    false,
"Other Actions":
    false,
"Import from File":
    false,
"Webhooks":
    false,

// ---- history-model
// ---- history-view
"This history is empty" :
    false,
"No matching datasets found" :
    false,
"An error occurred while getting updates from the server" :
    false,
"Please contact a Galaxy administrator if the problem persists" :
    false,
//TODO:
//"An error was encountered while <% where %>" :
//false,
"search datasets" :
    false,
"You are currently viewing a deleted history!" :
    false,
"You are over your disk quota" :
    false,
"Tool execution is on hold until your disk usage drops below your allocated quota" :
    false,
"All" :
    false,
"None" :
    false,
"For all selected" :
    false,

// ---- history-view-edit
"Edit history tags" :
    false,
"Edit history Annotation" :
    false,
"Click to rename history" :
    false,
// multi operations
"Operations on multiple datasets" :
    false,
"Hide datasets" :
    false,
"Unhide datasets" :
    false,
"Delete datasets" :
    false,
"Undelete datasets" :
    false,
"Permanently delete datasets" :
    false,
"This will permanently remove the data in your datasets. Are you sure?" :
    false,

// ---- history-view-annotated
"Dataset" :
    false,
"Annotation" :
false,

// ---- history-view-edit-current
"This history is empty. Click 'Get Data' on the left tool menu to start" :
    false,
"You must be logged in to create histories" :
    false,
//TODO:
//"You can <% loadYourOwn %> or <% externalSource %>" :
//false,
//"load your own data" :
//false,
//"get data from an external source" :
//false,

// these aren't in zh/ginga.po and the template doesn't localize
//"Include Deleted Datasets" :
//false,
//"Include Hidden Datasets" :
//false,


// ---------------------------------------------------------------------------- datasets
// ---- hda-model
"Unable to purge dataset" :
    false,

// ---- hda-base
// display button
"Cannot display datasets removed from disk" :
    false,
"This dataset must finish uploading before it can be viewed" :
    false,
"This dataset is not yet viewable" :
    false,
"View data" :
    false,
// download button
"Download" :
    false,
"Download dataset" :
    false,
"Additional files" :
    false,
// info/show_params
"View details" :
    false,

// dataset states
// state: new
"This is a new dataset and not all of its data are available yet" :
    false,
// state: noPermission
"You do not have permission to view this dataset" :
    false,
// state: discarded
"The job creating this dataset was cancelled before completion" :
    false,
// state: queued
"This job is waiting to run" :
    false,
// state: upload
"This dataset is currently uploading" :
    false,
// state: setting_metadata
"Metadata is being auto-detected" :
    false,
// state: running
"This job is currently running" :
    false,
// state: paused
"This job is paused. Use the \"Resume Paused Jobs\" in the history menu to resume" :
    false,
// state: error
"An error occurred with this dataset" :
    false,
// state: empty
"No data" :
    false,
// state: failed_metadata
"An error occurred setting the metadata for this dataset" :
    false,

// ajax error prefix
"There was an error getting the data for this dataset" :
    false,

// purged'd/del'd msg
"This dataset has been deleted and removed from disk" :
    false,
"This dataset has been deleted" :
    false,
"This dataset has been hidden" :
    false,

"format" :
    false,
"database" :
    false,

// ---- hda-edit
"Edit attributes" :
    false,
"Cannot edit attributes of datasets removed from disk" :
    false,
"Undelete dataset to edit attributes" :
    false,
"This dataset must finish uploading before it can be edited" :
    false,
"This dataset is not yet editable" :
    false,

"Delete" :
    false,
"Dataset is already deleted" :
    false,

"View or report this error" :
    false,

"Run this job again" :
    false,

"Visualize" :
    false,
"Visualize in" :
    false,

"Undelete it" :
    false,
"Permanently remove it from disk" :
    false,
"Unhide it" :
    false,

"You may be able to" :
    false,
"set it manually or retry auto-detection" :
    false,

"Edit dataset tags" :
    false,
"Edit dataset annotation" :
    false,

"Tool Help" :
    false,

// ---------------------------------------------------------------------------- admin
"Search Tool Shed":
    false,
"Monitor installing repositories":
    false,
"Manage installed tools":
    false,
"Reset metadata":
    false,
"Download local tool":
    false,
"Tool lineage":
    false,
"Reload a tool's configuration":
    false,
"Review tool migration stages":
    false,
"View Tool Error Logs":
    false,
"Manage Display Whitelist":
    false,
"Manage Tool Dependencies":
    false,
"Users":
    false,
"Groups":
    false,
"API keys":
    false,
"Impersonate a user":
    false,
"Data":
    false,
"Quotas":
    false,
"Roles":
    false,
"Local data":
    false,
"Form Definitions":
    false,

// ---------------------------------------------------------------------------- Scratchbook
"Enable/Disable Scratchbook":
    false,
"Show/Hide Scratchbook":
    false,

// ---------------------------------------------------------------------------- misc. MVC
"Tags" :
    false,
"Edit annotation" :
    false,


// ----------------------------------------------------------------------------
},
    'ja' : true,
    'fr' : true,
    'zh' : true
});
