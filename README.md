# Batch update Evernote note creation dates
This Python script is an Evernote note date updater that works with your Evernote API credentials (consumer key and secret). It automates the process of updating the creation dates for multiple notes in a specific notebook.

The script works by:

1. Connecting to your Evernote account using OAuth authentication
2. Finding a specific notebook
3. Looking at each note's title for an 8-digit date (YYYYMMDD format)
4. Changing the note's creation date to match the date found in the title
5. Showing you progress as it works through all notes

It's particularly useful if you have many notes with dates in their titles that you want to reorganize chronologically in Evernote. Instead of manually changing each creation date (which would be tedious for hundreds of notes), this script automates the entire process.

The script includes safety features like asking for confirmation before making changes, showing you what it's about to do for each note, and providing a summary at the end of how many notes were updated successfully.

# Prerequisites

1. Get your developer API key and secret from: [Evernote Developer](https://dev.evernote.com/doc/)
2. Download and install the [Evernote SDK for Python](https://dev.evernote.com/doc/start/python.php)
3. Move the notes you want to update into a specific notebook
4. Ensure the following Python packages are installed
```
pip install distutils
pip install httplib2
pip install oauth2
pip install pyperclip
pip install pyutil
```

# Installation instructions

1. Install the Evernote SDK, if you haven't already: `pip install evernote3`
2. If that doesn't work, try installing directly from GitHub: `pip install git+https://github.com/evernote/evernote-sdk-python3.git`
3. Update the script:
   + Replace `YOUR-CONSUMER-KEY` with your actual consumer key
   + Replace `YOUR-CONSUMER-SECRET` with your actual consumer secret
4. Run the script: `python change-created-date.py`
5. Follow the on-screen prompts

# Rate limit, be prepared

You will exceed Evernote's API rate limit quickly, if you are updating more than 20 notes at a time. 

Don't worry, the script recognizes when the rate limit is exceeded and will wait for the time to pass before retrying. 

Tip: Let the script run in the background while you do other tasks on or off your computer. Once you initiate the script and agree to update the collection of notes, there are no other prompts you need to worry about.
