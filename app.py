import os
import random
import string
# FIX 1: Added 'after_this_request' to the import list
from flask import Flask, request, render_template_string, send_file, redirect, url_for, after_this_request
import sys
import time
import traceback 
from reportlab.lib.units import inch

# Import the generation function from the external script
# We make the import non-fatal to allow the server to start and display the error message.
try:
    from generator import generate_word_search_pdf
except ImportError as e:
    # Set a flag and store the error message if the import fails
    generate_word_search_pdf = None
    GENERATOR_IMPORT_ERROR = str(e)
except Exception as e:
    generate_word_search_pdf = None
    GENERATOR_IMPORT_ERROR = f"An unexpected error occurred during generator load: {e}"

# --- Configuration ---
app = Flask(__name__)
# Create a temporary directory for PDF output
TEMP_DIR = os.path.join(os.getcwd(), 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

# --- HTML Template (Embedded for simplicity) ---

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KDP Word Search Generator</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #f7f7f7; }
        .card { box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }
    </style>
</head>
<body class="p-4 sm:p-8">
    <div class="max-w-4xl mx-auto">
        <header class="text-center mb-10">
            <h1 class="text-4xl font-extrabold text-indigo-700">Word Search Puzzle Generator</h1>
            <p class="text-gray-600 mt-2">Generate Large Print, KDP-Ready Word Search collections using custom parameters.</p>
        </header>

        {% if error_message %}
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6" role="alert">
            <strong class="font-bold">Error:</strong>
            <span class="block sm:inline">{{ error_message }}</span>
        </div>
        {% endif %}

        {% if generator_missing %}
        <div class="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded relative mb-6" role="alert">
            <strong class="font-bold">Setup Error:</strong>
            <span class="block sm:inline">The generator function is missing. Please ensure 'generator.py' is correctly placed and committed. Import Error: {{ generator_error }}</span>
        </div>
        {% endif %}

        <div class="card bg-white p-6 sm:p-8 rounded-xl border border-gray-200">
            <form method="POST" action="{{ url_for('generate') }}" class="grid grid-cols-1 md:grid-cols-2 gap-6">

                <div class="md:col-span-2">
                    <label for="themes" class="block text-sm font-medium text-gray-700">Themes (Comma Separated)</label>
                    <input type="text" name="themes" id="themes" required
                        value="{{ default_params.themes }}"
                        placeholder="e.g., animals, safari, jungle"
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-3 border">
                    <p class="mt-1 text-xs text-gray-500">The script will fetch related words for these themes online.</p>
                </div>

                <div>
                    <label for="word_count" class="block text-sm font-medium text-gray-700">Total Words to Collect</label>
                    <input type="number" name="word_count" id="word_count" required
                        value="{{ default_params.word_count }}" min="20" max="2000"
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-3 border">
                    <p class="mt-1 text-xs text-gray-500">Total number of words to be distributed across all puzzles.</p>
                </div>

                <div>
                    <label for="size" class="block text-sm font-medium text-gray-700">Puzzle Grid Size (N x N)</label>
                    <input type="number" name="size" id="size" required
                        value="{{ default_params.size }}" min="10" max="25"
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-3 border">
                    <p class="mt-1 text-xs text-gray-500">The grid will be N x N (e.g., 15 for 15x15).</p>
                </div>
                
                <div>
                    <label for="page_size" class="block text-sm font-medium text-gray-700">PDF Page Size</label>
                    <select name="page_size" id="page_size" required
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-3 border appearance-none bg-white">
                        <option value="letter" {% if default_params.page_size == 'letter' %}selected{% endif %}>Letter (8.5 x 11 in - Standard KDP)</option>
                        <option value="A4" {% if default_params.page_size == 'A4' %}selected{% endif %}>A4 (International)</option>
                        <option value="legal" {% if default_params.page_size == 'legal' %}selected{% endif %}>Legal (8.5 x 14 in)</option>
                    </select>
                    <p class="mt-1 text-xs text-gray-500">Physical paper size of the output PDF.</p>
                </div>

                <div class="md:col-span-2 mt-4">
                    <button type="submit" {% if generator_missing %}disabled{% endif %}
                        class="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-lg text-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition duration-150 ease-in-out transform hover:scale-105 {% if generator_missing %}opacity-50 cursor-not-allowed{% endif %}">
                        <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" style="display:none;" fill="none" viewBox="0 0 24 24" id="spinner">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Generate and Download PDF
                    </button>
                </div>
            </form>
        </div>
        
        <footer class="text-center text-xs text-gray-400 mt-8">
            <p>Word fetching uses Datamuse & ConceptNet APIs.</p>
        </footer>

    </div>
    
    <script>
        // Simple client-side loading indicator management
        const form = document.querySelector('form');
        const button = form.querySelector('button');
        const spinner = document.getElementById('spinner');

        form.addEventListener('submit', () => {
            button.disabled = true;
            button.classList.add('bg-indigo-400');
            // Show the spinner and update text
            spinner.style.display = 'inline';
            button.innerHTML = '<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Generating... Please Wait (up to 30s)';
        });
    </script>
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main configuration form."""
    default_params = {
        'themes': 'animals, space, food',
        'word_count': 100,
        'size': 15,
        'page_size': 'letter'
    }
    
    # Check if the generator failed to load
    if generate_word_search_pdf is None:
        return render_template_string(HTML_TEMPLATE, 
                                      default_params=default_params,
                                      generator_missing=True,
                                      generator_error=globals().get('GENERATOR_IMPORT_ERROR', 'Unknown error'))

    return render_template_string(HTML_TEMPLATE, default_params=default_params, generator_missing=False)

@app.route('/generate', methods=['POST'])
def generate():
    """Handles form submission, runs the Python script, and serves the PDF."""
    
    # Critical check: Ensure generator loaded successfully
    if generate_word_search_pdf is None:
        error_msg = f"Application initialization failed. Please check 'generator.py' in the logs. Error: {globals().get('GENERATOR_IMPORT_ERROR', 'Unknown load failure.')}"
        return render_template_string(HTML_TEMPLATE, default_params=request.form.to_dict(), error_message=error_msg), 500

    final_pdf_path = "" # Initialize here for cleanup in the final except block

    try:
        # 1. Parse and Validate Parameters
        themes = request.form.get('themes', 'random').strip()
        word_count = int(request.form.get('word_count', 100))
        size = int(request.form.get('size', 15))
        page_size_str = request.form.get('page_size', 'letter')
        
        if not themes:
            raise ValueError("Themes field cannot be empty.")
        if not (10 <= size <= 25):
            raise ValueError("Puzzle size must be between 10 and 25.")
        if not (20 <= word_count <= 2000):
            raise ValueError("Word count must be between 20 and 2000.")

        # 2. Generate Unique Filename and Output Path
        session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        # Sanitize themes for filename
        safe_theme = "".join(c for c in themes.split(',')[0].strip() if c.isalnum()).lower()
        output_filename = f"word_search_collection_{safe_theme or 'puzzles'}_{session_id}.pdf"
        output_path = os.path.join(TEMP_DIR, output_filename)
        
        # 3. Execute the Python Puzzle Script
        # The core call to your generator script
        final_pdf_path = generate_word_search_pdf(
            width=size,
            height=size,
            themes=themes,
            word_count=word_count,
            page_size_str=page_size_str,
            output_path=output_path
        )
        
        # FIX 2: Corrected the decorator usage to use the imported function, not an app attribute.
        @after_this_request
        def cleanup(response):
            """Schedules the temporary file deletion after the response is sent."""
            if os.path.exists(final_pdf_path):
                try:
                    os.remove(final_pdf_path)
                    print(f"✅ Cleaned up temp file: {final_pdf_path}", file=sys.stderr)
                except Exception as cleanup_e:
                    print(f"⚠️ Error cleaning up temp file {final_pdf_path}: {cleanup_e}", file=sys.stderr)
            return response

        # 4. Serve the File to the User
        # Returning this response stops the spinner and initiates the download
        return send_file(
            final_pdf_path, 
            mimetype='application/pdf', 
            as_attachment=True, 
            download_name=output_filename
        )

    except ValueError as e:
        # Re-render the form with user's inputs and an error message
        default_params = request.form.to_dict()
        return render_template_string(HTML_TEMPLATE, default_params=default_params, error_message=str(e)), 400

    except Exception as e:
        # General Server/Generation Errors
        
        # Capture the full traceback and print it to standard error (which Render logs)
        error_trace = traceback.format_exc()
        print("--- FULL PDF GENERATION TRACEBACK START ---", file=sys.stderr)
        print(error_trace, file=sys.stderr)
        print("--- FULL PDF GENERATION TRACEBACK END ---", file=sys.stderr)
        
        # Try to clean up the file if it was partially created during an exception
        if final_pdf_path and os.path.exists(final_pdf_path):
            try:
                os.remove(final_pdf_path)
            except OSError:
                pass 

        # This is what the user sees in the browser
        error_msg = f"Generation failed due to a server error. Please check your themes. Error: {type(e).__name__}: {e}"
        
        return render_template_string(HTML_TEMPLATE, default_params=request.form.to_dict(), error_message=error_msg), 500
        
if __name__ == '__main__':
    # When running locally, you can change the port if 5000 is used
    app.run(debug=True, port=5000)
