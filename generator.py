import csv
from word_search_generator import WordSearch
import io
import contextlib
import sys
import random
import requests
import os
from reportlab.lib.pagesizes import letter, A4, legal
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import lightgrey
from reportlab.lib import colors

# --- KDP Large Print Configuration ---
PAGE_SIZE_MAP = {
    'letter': letter,
    'A4': A4,
    'legal': legal,
}

# Configuration for PDF drawing
GRID_FONT = "Courier"
GRID_FONT_SIZE = 16
WORD_FONT = "Helvetica"
WORD_FONT_SIZE = 11
HEADING_FONT = "Helvetica-Bold"
HEADING_FONT_SIZE = 16
PAGE_NUMBER_FONT_SIZE = 9
BORDER_PADDING = 5
PUZZLE_TOP_OFFSET = 1.25 * inch
WORDS_SECTION_OFFSET = 1.0 * inch
MAX_WORDS_PER_PUZZLE = 20
LEFT_MARGIN = 0.75 * inch
RIGHT_MARGIN = 0.75 * inch

# API Keys
WORDNIK_API_KEY = "" # Leave blank until available

def fetch_expanded_theme_words(themes, target_count=1920):
    """Fetch expanded unique themed words using multiple comma-separated themes."""
    
    def fetch_from_datamuse(theme):
        # Placeholder: Actual Datamuse fetching logic
        print(f"[Datamuse] Fetching words for {theme}")
        results = set()
        endpoints = [
            f"https://api.datamuse.com/words?ml={theme}&max=225",
            f"https://api.datamuse.com/words?topics={theme}&max=225",
        ]
        for url in endpoints:
            try:
                # Use a small timeout to avoid hanging the web server
                r = requests.get(url, timeout=3) 
                if r.status_code == 200:
                    data = r.json()
                    for w in data:
                        word = w.get("word", "").upper()
                        # Basic filtering
                        if word.isalpha() and 3 < len(word) <= 12: 
                            results.add(word)
            except Exception as e:
                print(f"⚠️ Datamuse error ({theme}): {e}", file=sys.stderr)
        return list(results)

    def fetch_from_conceptnet(theme):
        # Placeholder: Actual ConceptNet fetching logic
        print(f"[ConceptNet] Fetching words for {theme}")
        results = set()
        url = f"https://api.conceptnet.io/related/c/en/{theme}?filter=/c/en&limit=1000"
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                data = r.json()
                if 'related' in data:
                    for item in data['related']:
                        term = item.get('@id', '')
                        if term.startswith('/c/en/'):
                            word = term.split('/c/en/')[-1].replace('_', '').upper()
                            if word.isalpha() and 3 < len(word) <= 12:
                                results.add(word)
        except Exception as e:
            print(f"⚠️ ConceptNet error ({theme}): {e}", file=sys.stderr)
        return list(results)

    all_results = set()
    theme_list = [t.strip() for t in themes.split(',') if t.strip()]

    for theme in theme_list:
        d_words = fetch_from_datamuse(theme)
        c_words = fetch_from_conceptnet(theme)
        combined_theme_words = list(set(d_words + c_words))
        all_results.update(combined_theme_words)

    combined = list(all_results)
    random.shuffle(combined)

    print(f"✅ Retrieved {len(combined)} unique words across all themes: {', '.join(theme_list)}")
    return combined[:target_count]

def split_word_list(words):
    """Splits a long list of words into chunks for individual puzzles."""
    return [words[i:i + MAX_WORDS_PER_PUZZLE] for i in range(0, len(words), MAX_WORDS_PER_PUZZLE)]

def draw_wrapped_lines(pdf, text, x, y, font, size, line_h, page_w, page_h, margin_left, margin_right, margin_bottom):
    """Draws text and wraps it within the page boundaries."""
    # FIX: Handle empty/whitespace input to prevent ReportLab errors
    if not text or not text.strip():
        return y 

    pdf.setFont(font, size)
    words = text.split()
    max_width = page_w - margin_left - margin_right
    current_line = ""
    
    # Handle the case where Y is already too low (unlikely but safe)
    if y < margin_bottom:
        return y
        
    for word in words:
        test_line = f"{current_line} {word}".strip()
        # ReportLab stringWidth returns the width of the string in the current font
        if pdf.stringWidth(test_line, font, size) > max_width:
            pdf.drawString(margin_left, y, current_line)
            y -= line_h
            if y < margin_bottom:
                # Do not showPage here, let the caller handle new pages
                pdf.setFont(font, size)
                return y # Signal to the caller that the page space is exhausted
            current_line = word
        else:
            current_line = test_line
    if current_line:
        pdf.drawString(margin_left, y, current_line)
        y -= line_h
    return y

def draw_grid(pdf, puzzle, page_w, page_h, margin, highlight=False):
    """Draws the word search grid and optional solution highlight."""
    pdf.setFont(GRID_FONT, GRID_FONT_SIZE)
    
    # --- Grid Sizing and Positioning ---
    
    # Measure the width of a single character and space in the grid font
    char_width = pdf.stringWidth("A", GRID_FONT, GRID_FONT_SIZE)
    space_width = pdf.stringWidth(" ", GRID_FONT, GRID_FONT_SIZE)
    
    # Calculate total line width: N characters + (N-1) spaces
    line_width = (puzzle.size * char_width) + ((puzzle.size - 1) * space_width) 
    
    # Calculate vertical spacing
    line_height = GRID_FONT_SIZE + 2 # Add a couple of points for spacing
    grid_height = puzzle.size * line_height

    x0 = (page_w - line_width) / 2
    y0 = page_h - PUZZLE_TOP_OFFSET - grid_height

    # --- Draw Border ---
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(1)
    # The rect needs to encompass the whole grid plus the padding
    pdf.rect(x0 - BORDER_PADDING, y0 - BORDER_PADDING, 
             line_width + 2 * BORDER_PADDING, grid_height + 2 * BORDER_PADDING)

    # --- Draw Grid Content ---
    y = y0 + grid_height - (line_height / 2) # Start Y for the first line of text baseline
    
    for r in range(puzzle.size):
        line = " ".join(puzzle.puzzle[r])
        
        # Calculate X position for drawing characters individually (needed for highlight)
        current_x = x0
        
        for c in range(puzzle.size):
            cell_text = puzzle.puzzle[r][c]
            
            # 1. Highlighting (Draw Rectangles First)
            if highlight:
                
                # --- Simple Highlight Drawing (Less accurate but visually functional) ---
                cell_is_highlighted = False
                
                # --- FIX: Check for 'start' and 'end' keys before accessing them (Line 190 fix) ---
                for word_info in puzzle.key.values():
                    # Only process word placement information if it's complete
                    if 'start' in word_info and 'end' in word_info:
                        sr, sc = word_info['start']
                        er, ec = word_info['end']
                        
                        # We only check the grid content itself, not a complex path trace.
                        # This relies on the library's internal key structure.
                        # The library provides the start and end indices of the word in the puzzle.
                        if (r, c) == (sr, sc) or (r, c) == (er, ec):
                            cell_is_highlighted = True
                            break
                        # Complex path checking is omitted for stability.
                        
                if cell_is_highlighted:
                    # Calculate character position within the line
                    rect_x = current_x - (space_width / 2)
                    rect_y = y - line_height + (line_height - GRID_FONT_SIZE) / 2
                    
                    pdf.setFillColor(lightgrey)
                    pdf.rect(rect_x, rect_y, char_width + space_width, line_height, fill=1, stroke=0)
                    pdf.setFillColor(colors.black)
                        
            # 2. Drawing Character
            pdf.drawString(current_x, y, cell_text)
            
            # Advance X position for the next character (char + space)
            current_x += char_width + space_width
            
        # Advance Y position for the next line
        y -= line_height
        
    return y0

def add_page_number(pdf, page_w, margin, page_num):
    """Adds a page number to the bottom right."""
    pdf.setFont(WORD_FONT, PAGE_NUMBER_FONT_SIZE)
    pdf.drawRightString(page_w - margin, 0.5 * inch, str(page_num))

def generate_word_search_pdf(width: int, height: int, themes: str, word_count: int, page_size_str: str, output_path: str):
    """
    Main function to generate the Word Search PDF based on user parameters.
    """
    
    # 1. Setup
    global THEME 
    THEME = themes.split(',')[0].strip().capitalize() if themes else "Themed"
    page_size = PAGE_SIZE_MAP.get(page_size_str, letter)
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 2. Fetch Words
    # We fetch a large pool of words and then distribute them
    all_words = fetch_expanded_theme_words(themes, target_count=word_count)

    if not all_words:
        # Raise an exception that Flask will catch and display to the user
        raise Exception("Word list generation failed. Try a different theme or reduce the word count.")

    # --- CRITICAL FIX: AGGRESSIVE ASCII SANITIZATION ---
    # This was added in the previous step to handle character encoding issues.
    sanitized_words = []
    for word in all_words:
        # Aggressively remove non-ASCII characters that ReportLab may choke on.
        cleaned_word = word.encode('ascii', 'ignore').decode('ascii').strip().upper()
        
        # Final check to ensure it's still a valid word after cleaning
        if cleaned_word.isalpha() and 3 < len(cleaned_word) <= 12:
            sanitized_words.append(cleaned_word)
            
    all_words = sanitized_words
    
    if not all_words:
         # This will catch cases where all words are removed because they contain non-ASCII characters.
         raise Exception("Word list generation failed after sanitization. Try a theme with common English words.")
    # --------------------------------------------------


    # 3. Create Puzzles
    puzzle_sets = [sorted(chunk) for chunk in split_word_list(all_words)]
    print(f"Generating {len(puzzle_sets)} puzzles...")

    puzzles = []
    for i, words in enumerate(puzzle_sets, 1):
        words_str = ", ".join(words)
        # Use the larger of width/height for the square puzzle size
        puzzle_size = max(width, height)
        
        # Suppress stdout/stderr during puzzle generation as it can be noisy
        with contextlib.redirect_stdout(sys.stderr):
            # The library can raise a GenerationError if it can't fit all words
            try:
                puzzle = WordSearch(words_str, size=puzzle_size, level=3) # Difficulty level is 3 (medium)
                puzzle.index = i
                puzzles.append({'puzzle': puzzle, 'words': words})
            except Exception as e:
                print(f"⚠️ Could not generate puzzle #{i} with words: {words}. Skipping. Error: {e}")
                # Log this error but continue with the next puzzle if possible

    if not puzzles:
         raise Exception("Could not successfully generate any puzzles with the provided words and size.")


    # 4. Generate PDF
    c = canvas.Canvas(output_path, pagesize=page_size)
    page_w, page_h = page_size
    margin = LEFT_MARGIN 
    page_number = 1
    line_h = 14 # Standard line height for word lists

    # --- PUZZLE PAGES ---
    for p in puzzles:
        puzzle = p['puzzle']
        words = p['words']

        # Title
        y_top = page_h - margin
        c.setFont(HEADING_FONT, HEADING_FONT_SIZE)
        title_prefix = f"{THEME} " if THEME else ""
        c.drawCentredString(page_w / 2, y_top, f"{title_prefix}Word Search Puzzle #{puzzle.index}")

        # Grid
        # draw_grid returns the Y coordinate of the bottom of the grid area
        grid_bottom_y = draw_grid(c, puzzle, page_w, page_h, margin)

        # Word List Header
        y_current = grid_bottom_y - WORDS_SECTION_OFFSET
        c.setFont(HEADING_FONT, 12)
        c.drawString(LEFT_MARGIN, y_current, "Words to Find (Alphabetical):")
        y_current -= line_h # Move to the start of the word list

        # Word List
        # margin_bottom: ensure we leave space for the page number
        margin_bottom = 0.5 * inch + 20 
        y_current = draw_wrapped_lines(c, ", ".join(words), LEFT_MARGIN, y_current, 
                                       WORD_FONT, WORD_FONT_SIZE, line_h, 
                                       page_w, page_h, LEFT_MARGIN, RIGHT_MARGIN, margin_bottom)
        
        # Footer and Page Turn
        add_page_number(c, page_w, margin, page_number)
        page_number += 1
        c.showPage()

    # --- ANSWER KEY PAGES ---
    for p in puzzles:
        puzzle = p['puzzle']
        words = p['words']

        # Title
        y_top = page_h - margin
        c.setFont(HEADING_FONT, HEADING_FONT_SIZE)
        title_prefix = f"{THEME} " if THEME else ""
        c.drawCentredString(page_w / 2, y_top, f"{title_prefix}Puzzle #{puzzle.index} – Answer Key")

        # Grid (Highlighted)
        draw_grid(c, puzzle, page_w, page_h, margin, highlight=True)

        # Word List (for reference)
        y_bottom = margin + 60
        c.setFont(HEADING_FONT, 12)
        c.drawString(LEFT_MARGIN, y_bottom, "Answer Key Word List:")
        y_bottom -= line_h
        draw_wrapped_lines(c, ", ".join(words), LEFT_MARGIN, y_bottom, 
                           WORD_FONT, WORD_FONT_SIZE, line_h, 
                           page_w, page_h, LEFT_MARGIN, RIGHT_MARGIN, margin)

        # Footer and Page Turn
        add_page_number(c, page_w, margin, page_number)
        page_number += 1
        c.showPage()

    c.save()
    print(f"✅ All puzzles saved to {output_path}")
    return output_path

if __name__ == "__main__":
    # Example usage for local testing
    output_pdf = os.path.join("temp", "test_word_search.pdf")
    # Make sure 'temp' directory exists locally
    os.makedirs(os.path.dirname(output_pdf), exist_ok=True) 
    generate_word_search_pdf(15, 15, "ocean, fish, boats", 40, 'letter', output_pdf)
