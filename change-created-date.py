import datetime
import re
import time
import webbrowser
import random
import inspect
import http.server
import socketserver
import threading
import urllib.parse
import pyperclip  # For clipboard functionality

# Add compatibility shim for Python 3.11+
if not hasattr(inspect, 'getargspec'):
    inspect.getargspec = inspect.getfullargspec

from evernote.api.client import EvernoteClient
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.edam.error.ttypes import EDAMSystemException, EDAMErrorCode

# API Configuration - Replace with your values
CONSUMER_KEY = 'YOUR-CONSUMER-KEY'
CONSUMER_SECRET = 'YOUR-CONSUMER-SECRET'
SANDBOX = False  # Set to False for production

# Rate limiting configuration
INITIAL_BACKOFF = 2  # Initial backoff time in seconds
MAX_BACKOFF = 60     # Maximum backoff time in seconds
MAX_RETRIES = 5      # Maximum number of retries per operation
BATCH_SIZE = 10      # Process notes in batches of this size

# OAuth callback server
class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET request to the callback URL"""
        # Parse the query string
        query = urllib.parse.urlparse(self.path).query
        params = dict(urllib.parse.parse_qsl(query))
        
        # Check if the oauth_verifier is present
        if 'oauth_verifier' in params:
            oauth_verifier = params['oauth_verifier']
            # Make the oauth_verifier available to the main thread
            self.server.oauth_verifier = oauth_verifier
            
            # Send a response to the browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Create a simple HTML page with the verification code
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Evernote Authentication</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ccc; border-radius: 5px; }}
                    .code {{ font-size: 24px; font-weight: bold; margin: 20px 0; padding: 10px; background-color: #f0f0f0; border-radius: 3px; }}
                    .success {{ color: green; }}
                    button {{ padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; }}
                    button:hover {{ background-color: #45a049; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Evernote Authentication Successful</h1>
                    <p>Your verification code is:</p>
                    <div class="code">{oauth_verifier}</div>
                    <p class="success">✓ This code has been automatically copied to your clipboard!</p>
                    <p>You can now return to the terminal to continue.</p>
                    <button onclick="window.close()">Close Window</button>
                </div>
                <script>
                    // Copy the verification code to the clipboard
                    try {{
                        navigator.clipboard.writeText("{oauth_verifier}");
                    }} catch (err) {{
                        console.error('Failed to copy: ', err);
                    }}
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            # If no oauth_verifier is present, send a generic response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authentication callback received, but no verification code found.")

    def log_message(self, format, *args):
        """Suppress server logs"""
        return

def start_oauth_callback_server(port=8080):
    """Start a temporary HTTP server to handle OAuth callback"""
    server = socketserver.TCPServer(("localhost", port), OAuthCallbackHandler)
    server.oauth_verifier = None
    
    # Start the server in a separate thread
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    return server

def get_access_token():
    """Get OAuth access token using the consumer key and secret"""
    print("Starting OAuth authentication process...")
    
    # Start the callback server
    callback_port = 8080
    callback_url = f"http://localhost:{callback_port}"
    server = start_oauth_callback_server(callback_port)
    
    client = EvernoteClient(
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        sandbox=SANDBOX
    )
    
    # Get the request token
    request_token = client.get_request_token(callback_url)
    
    # Generate the authorization URL
    authorize_url = client.get_authorize_url(request_token)
    
    # Open browser to authorize the application
    print("Opening browser for Evernote authorization...")
    print(f"Authorization URL: {authorize_url}")
    webbrowser.open(authorize_url)
    
    # Wait for the callback to be received
    print("\nWaiting for authentication in browser...")
    print("(If the browser doesn't open automatically, please copy and paste the URL above)")
    
    # Wait for the oauth_verifier with a timeout
    max_wait_time = 300  # 5 minutes
    wait_interval = 1
    elapsed_time = 0
    
    while server.oauth_verifier is None and elapsed_time < max_wait_time:
        time.sleep(wait_interval)
        elapsed_time += wait_interval
    
    # Stop the server
    server.shutdown()
    
    if server.oauth_verifier:
        oauth_verifier = server.oauth_verifier
        print(f"Authentication successful! Verification code: {oauth_verifier}")
        
        # Try to copy to clipboard
        try:
            pyperclip.copy(oauth_verifier)
            print("Verification code copied to clipboard!")
        except Exception as e:
            print(f"Could not copy to clipboard: {e}")
            print("Please copy the verification code manually.")
    else:
        print("\nAuthentication timed out or failed.")
        print("Please enter the verification code manually.")
        oauth_verifier = input("Enter the verification code: ")
    
    # Get the access token using the verification code
    try:
        access_token = client.get_access_token(
            request_token['oauth_token'],
            request_token['oauth_token_secret'],
            oauth_verifier
        )
        return access_token
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None

def extract_date_from_title(title):
    """Extract 8-digit date from note title and convert to timestamp"""
    date_match = re.search(r'(\d{8})', title)
    if not date_match:
        return None
    
    date_str = date_match.group(1)
    try:
        # Convert YYYYMMDD to datetime
        date = datetime.datetime.strptime(date_str, '%Y%m%d')
        # Convert to Unix timestamp (milliseconds)
        return int(date.timestamp() * 1000)
    except ValueError:
        return None

def api_call_with_backoff(func, *args, **kwargs):
    """Execute an API call with exponential backoff for rate limit errors"""
    backoff = INITIAL_BACKOFF
    retries = 0
    
    while retries < MAX_RETRIES:
        try:
            return func(*args, **kwargs)
        except EDAMSystemException as e:
            if e.errorCode == EDAMErrorCode.RATE_LIMIT_REACHED:
                rate_limit_duration = e.rateLimitDuration
                wait_time = rate_limit_duration if rate_limit_duration else backoff
                
                print(f"\nRate limit reached. Waiting for {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                
                # Increase backoff for next potential retry
                backoff = min(backoff * 2, MAX_BACKOFF)
                retries += 1
                
                # Add some jitter to avoid thundering herd problem
                jitter = random.uniform(0.5, 1.5)
                time.sleep(backoff * jitter - backoff)
            else:
                # For other Evernote API errors, just raise
                raise
        except Exception as e:
            # For non-Evernote errors, just raise
            raise
    
    # If we've exhausted our retries
    raise Exception(f"Failed after {MAX_RETRIES} retries due to rate limiting")

def get_notebook_guid(note_store, notebook_name):
    """Find the GUID of the specified notebook"""
    try:
        notebooks = note_store.listNotebooks()
        for notebook in notebooks:
            if notebook.name == notebook_name:
                return notebook.guid
        print(f"Notebook '{notebook_name}' not found. Available notebooks:")
        for notebook in notebooks:
            print(f"- {notebook.name}")
        return None
    except Exception as e:
        print(f"Error listing notebooks: {e}")
        return None

def update_note_dates():
    """Main function to update note creation dates"""
    print("Starting Evernote note date updater using OAuth...")
    
    # Get access token
    access_token = get_access_token()
    if not access_token:
        print("Failed to get access token. Please try again.")
        return
    
    # Create a new client with the access token
    client = EvernoteClient(token=access_token, sandbox=SANDBOX)
    note_store = client.get_note_store()
    
    # Test connection
    try:
        user = api_call_with_backoff(client.get_user_store().getUser)
        print(f"Connected to Evernote as: {user.username}")
    except Exception as e:
        print(f"Error authenticating with Evernote: {e}")
        return
    
    # Prompt user for notebook name
    print("\nRetrieving available notebooks...")
    try:
        notebooks = api_call_with_backoff(note_store.listNotebooks)
        print("Available notebooks:")
        for i, notebook in enumerate(notebooks, 1):
            print(f"{i}. {notebook.name}")
        
        # Get user selection
        while True:
            notebook_input = input("\nEnter notebook name or number to process: ")
            
            # Check if input is a number
            if notebook_input.isdigit():
                index = int(notebook_input) - 1
                if 0 <= index < len(notebooks):
                    notebook_name = notebooks[index].name
                    notebook_guid = notebooks[index].guid
                    break
                else:
                    print(f"Invalid number. Please enter a number between 1 and {len(notebooks)}.")
            else:
                # Input is a name, try to find matching notebook
                notebook_guid = None
                for notebook in notebooks:
                    if notebook.name.lower() == notebook_input.lower():
                        notebook_name = notebook.name
                        notebook_guid = notebook.guid
                        break
                
                if notebook_guid:
                    break
                else:
                    print("Notebook not found. Please try again.")
    except Exception as e:
        print(f"Error listing notebooks: {e}")
        return
    
    print(f"Selected notebook: {notebook_name}")
    
    # Set up the search filter to only get the metadata we need
    note_filter = NoteFilter(notebookGuid=notebook_guid)
    spec = NotesMetadataResultSpec(includeTitle=True)
    
    # Get all notes in the notebook (just metadata first to save API calls)
    try:
        notes_metadata = api_call_with_backoff(
            note_store.findNotesMetadata, 
            note_filter, 0, 999999, spec
        )
    except Exception as e:
        print(f"Error retrieving notes: {e}")
        return
    
    # Process each note
    total_notes = notes_metadata.totalNotes
    processed = 0
    updated = 0
    errors = []
    
    print(f"Found {total_notes} notes to process")
    
    # Confirmation before proceeding
    confirm = input(f"Ready to update creation dates for {total_notes} notes? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return
    
    # Save a session file with progress
    session_file = f"evernote_update_progress_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Process notes in batches to reduce impact of rate limiting
    for i in range(0, len(notes_metadata.notes), BATCH_SIZE):
        batch = notes_metadata.notes[i:i+BATCH_SIZE]
        print(f"\nProcessing batch {(i//BATCH_SIZE)+1} of {(total_notes+BATCH_SIZE-1)//BATCH_SIZE}...")
        
        for note_meta in batch:
            processed += 1
            try:
                # Get the full note with minimal data (only need title and created date)
                note = api_call_with_backoff(
                    note_store.getNote, 
                    note_meta.guid, True, False, False, False
                )
                
                # Print current info
                current_date = datetime.datetime.fromtimestamp(note.created/1000)
                formatted_date = current_date.strftime('%Y-%m-%d %H:%M:%S')
                print(f"Processing {processed}/{total_notes}: {note.title} (Current date: {formatted_date})")
                
                # Extract date from title
                new_timestamp = extract_date_from_title(note.title)
                
                if new_timestamp:
                    # Only update if the date is actually different (reduces API calls)
                    if new_timestamp != note.created:
                        # Show what we're changing to
                        new_date = datetime.datetime.fromtimestamp(new_timestamp/1000)
                        new_formatted = new_date.strftime('%Y-%m-%d %H:%M:%S')
                        print(f"  → Updating to: {new_formatted}")
                        
                        # Update the note's creation timestamp
                        note.created = new_timestamp
                        api_call_with_backoff(note_store.updateNote, note)
                        updated += 1
                    else:
                        print(f"  → Date already matches {formatted_date}, skipping")
                else:
                    print(f"  → No valid date found in title, skipping")
            
            except Exception as e:
                error_msg = f"Error processing note {note_meta.title}: {str(e)}"
                print(f"  → {error_msg}")
                errors.append(error_msg)
            
            # Save progress to session file
            with open(session_file, 'a') as f:
                f.write(f"Processed {processed}/{total_notes}: {note_meta.title}\n")
        
        # Add a small delay between batches to be nice to the API
        if i + BATCH_SIZE < len(notes_metadata.notes):
            delay = random.uniform(1.0, 2.0)
            print(f"Waiting {delay:.1f} seconds before next batch...")
            time.sleep(delay)

    # Print summary
    print("\n====== SUMMARY ======")
    print(f"Total notes processed: {processed}")
    print(f"Notes updated: {updated}")
    print(f"Errors encountered: {len(errors)}")
    print(f"Progress log saved to: {session_file}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"- {error}")

if __name__ == "__main__":
    update_note_dates()
