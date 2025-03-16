# evernote-created-date
This script is an Evernote note date updater that works with your Evernote API credentials (consumer key and secret). It automates the process of updating the creation dates for multiple notes in a specific notebook.

The script works by:

1. Connecting to your Evernote account using OAuth authentication
2. Finding a specific notebook
3. Looking at each note's title for an 8-digit date (YYYYMMDD format)
4. Changing the note's creation date to match the date found in the title
5. Showing you progress as it works through all notes

It's particularly useful if you have many notes with dates in their titles that you want to reorganize chronologically in Evernote. Instead of manually changing each creation date (which would be tedious for hundreds of notes), this script automates the entire process.

The script includes safety features like asking for confirmation before making changes, showing you what it's about to do for each note, and providing a summary at the end of how many notes were updated successfully.
