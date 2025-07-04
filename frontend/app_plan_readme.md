# Describe the idea
The idea is to build Copilot Canvas with a layout that includes a top section to display ticket metadata and a bottom section with tabs for similar tickets, suggested solutions, and a Natural Language Interaction (Copilot) feature.


# Describe the app UI
The UI will have a top section displaying ticket metadata such as Problem/Cause/Actions Taken/Result, Status, Priority, Assigned Agent, Requester, Channel, Tags as colored badges, and Attachments with file name, icon, and a download button. There will be a 'View Details' button to show the full conversation history. The bottom section will have tabs for Similar Tickets (paginated list of related tickets), Suggested Solutions (paginated list of recommended solutions), and Copilot (Natural Language Interaction) with an input box to ask questions, checkboxes to filter content types (Tickets, Solutions, Images, Attachments), and a 'Search' button to trigger a backend query.


# List of core features
- Display ticket metadata including Problem/Cause/Actions Taken/Result, Status, Priority, Assigned Agent, Requester, Channel, Tags, Attachments
- Button to show full conversation history
- Tabs for Similar Tickets, Suggested Solutions, and Copilot (Natural Language Interaction)
- Backend integration with FastAPI backend endpoints



# Implementation Plan
## Describe the UI to be built for every placeholder
- Placeholder: ticket_sidebar in Freshdesk
The UI will have two sections: top section for ticket metadata (Problem/Cause/Actions/Result, Status, Priority, Agent, Requester, Channel, Tags, Attachments) with a 'View Details' button, and bottom section with tabs for Similar Tickets, Suggested Solutions, and Copilot with an input box and filters.


## Details on what and how to fetch installation parameters
Capture the FastAPI backend URL and API key as secure text fields during app installation.

## App Initialization: Register & Implement App Initialization
Register for 'app.activated' event in the ticket sidebar app and implement a handler that fetches ticket data using Data methods. Use the fetched ticket metadata to populate the app UI.

## View Details: Register & Implement View Details Button
Register click event on the 'View Details' button using the client.interface.click event and implement an event handler that fetches conversation history via client.data.get. Display the conversation history in a modal using client.interface.trigger with showModal.

## Tab Navigation: Register & Implement Tab Navigation
Register click event listeners on tab header elements and implement handler functions that hide/show content divs based on the selected tab to switch between Similar Tickets, Suggested Solutions, and Copilot tabs.

## Load Similar Tickets: Register & Implement Similar Tickets Loading
Implement a serverless handler that triggers on activation of Similar Tickets tab, makes API call to FastAPI backend using Request Template to fetch similar tickets based on the current ticket's data, and then updates the UI with the results.

## Load Suggested Solutions: Register & Implement Suggested Solutions Loading
Implement a handler for the 'Suggested Solutions' tab that makes an API call to the FastAPI backend using Request Template to fetch suggested solutions based on the ticket data. Once the data is received, update the UI to display the suggested solutions.

## Copilot Search: Register & Implement Copilot Search
Register a click event handler on the 'Search' button in the Copilot tab that will collect the user's query and any selected filters, then make an API call to the FastAPI backend using the Request Template to search for relevant data.

## Ticket Updated: Register & Implement Ticket Update Handler
Register for 'ticket.propertiesUpdated' event using client.events.on to listen for ticket property changes. Create a handler function that will refresh the app's UI by calling the renderApp function when ticket properties are updated.

## Download Attachment: Register & Implement Attachment Download
Register click event listeners on attachment download buttons to fetch attachment details using Data Methods and trigger download functionality. Use the attachment ID from the clicked button to retrieve attachment data and initiate the download process.

## File Structure
`app/scripts/app.js`: App Frontend Script
`app/modal.html`
`manifest.json`: Contains the app manifest
`config/iparams.json`: Contains the app parameters
`app/index.html`: Entry point for the app
`config/requests.json`: Api Request Description

## Steps to run the app
- Run "fdk validate" and make sure no errors are there
- Fix errors if any (can use copilot to fix (lint))
- Run "fdk run"
- Go to "http://localhost:3001" for iparams
- Go to "...?dev=true"
