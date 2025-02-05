import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import ollama
import threading
import time
import os
from tkinter import font
import re
import uuid

# Add constants at the top of the file:
SYNTAX_COLORS = {
    "keyword": "#FF7B72",
    "string": "#A5D6FF",
    "comment": "#8B949E",
    "function": "#D2A8FF",
    "number": "#79C0FF"
}

UI_FONTS = {
    "code": ("Consolas", 12),
    "chat": ("Segoe UI", 10)
}

class SyntaxHighlightingText(scrolledtext.ScrolledText):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tag_configure("keyword", foreground="#FF7B72")
        self.tag_configure("string", foreground="#A5D6FF")
        self.tag_configure("comment", foreground="#8B949E")
        self.tag_configure("function", foreground="#D2A8FF")
        self.tag_configure("number", foreground="#79C0FF")
        
        self.bind('<KeyRelease>', self.highlight_syntax)
        
    def highlight_syntax(self, event=None):
        # Add debouncing to prevent excessive updates
        if hasattr(self, '_highlight_timer'):
            self.after_cancel(self._highlight_timer)
        
        self._highlight_timer = self.after(500, self._do_highlight)

    def _do_highlight(self):
        # Remove all existing tags
        for tag in ["keyword", "string", "comment", "function", "number"]:
            self.tag_remove(tag, "1.0", "end")
        
        # Get visible lines only instead of entire content
        first_line = self.index("@0,0")
        last_line = self.index("@0,%d" % self.winfo_height())
        content = self.get(first_line, last_line)
        
        # Keywords
        keywords = ["def", "class", "import", "from", "return", "if", "else", "elif",
                   "try", "except", "finally", "for", "while", "in", "is", "None",
                   "True", "False", "and", "or", "not", "with", "as", "break",
                   "continue", "global", "lambda"]
        
        for keyword in keywords:
            start_index = first_line
            while True:
                start = self.search(r'\m' + keyword + r'\M', start_index, last_line, regexp=True)
                if not start:
                    break
                end = f"{start}+{len(keyword)}c"
                self.tag_add("keyword", start, end)
                start_index = end
                
        # Strings
        for match in re.finditer(pattern := r'(\".*?\"|\'.*?\')', content):
            start = f"{first_line}+{match.start()}c"
            end = f"{first_line}+{match.end()}c"
            self.tag_add("string", start, end)
            
        # Comments
        for match in re.finditer(r'#.*$', content, re.MULTILINE):
            start = f"{first_line}+{match.start()}c"
            end = f"{first_line}+{match.end()}c"
            self.tag_add("comment", start, end)
            
        # Functions
        for match in re.finditer(r'def\s+(\w+)\s*\(', content):
            start = f"{first_line}+{match.start(1)}c"
            end = f"{first_line}+{match.end(1)}c"
            self.tag_add("function", start, end)
            
        # Numbers
        for match in re.finditer(r'\b\d+\b', content):
            start = f"{first_line}+{match.start()}c"
            end = f"{first_line}+{match.end()}c"
            self.tag_add("number", start, end)

class CodeTab(ttk.Frame):
    """A tab containing a code editor with syntax highlighting"""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.code_editor = SyntaxHighlightingText(
            self,
            wrap=tk.NONE,
            font=UI_FONTS["code"],
            background='#0D1117',
            foreground='#C9D1D9',
            insertbackground='white'
        )
        self.code_editor.pack(expand=True, fill='both', padx=5, pady=5)

class ChatCodeEditor:
    """
    A code editor with integrated AI chat capabilities using the DeepSeek model.
    Provides syntax highlighting and real-time code suggestions.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("DeepSeek Code Assistant")
        self.root.geometry("1400x800")
        
        # Configure tab style
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[10, 2])
        style.configure('TNotebook', background='#0D1117')
        style.configure('TFrame', background='#0D1117')
        
        # Model settings
        self.model = 'deepseek-r1:14b'
        self.chat_history = []
        self.is_streaming = False
        self.current_response = ""
        
        self.setup_ui()
        self.setup_bindings()
        self.accumulated_response = ""  # Add this line to track full response
    
    def setup_ui(self):
        # Configure grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        
        # Create paned window
        self.paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.grid(row=0, column=0, columnspan=2, sticky="nsew")
        
        # Code Editor Frame with Notebook
        self.code_frame = ttk.Frame(self.paned_window)
        self.notebook = ttk.Notebook(self.code_frame)
        self.notebook.pack(expand=True, fill='both')
        
        # Create initial tab
        self.create_new_tab()
        
        self.paned_window.add(self.code_frame, weight=1)
        
        # Chat Frame
        self.chat_frame = ttk.Frame(self.paned_window)
        self.chat_window = scrolledtext.ScrolledText(
            self.chat_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            background='#0D1117',
            foreground='#C9D1D9'
        )
        self.chat_window.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Input Frame
        self.input_frame = ttk.Frame(self.chat_frame)
        self.user_entry = ttk.Entry(self.input_frame, font=('Segoe UI', 10))
        self.user_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        self.send_button = ttk.Button(self.input_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT, padx=5)
        
        self.cancel_button = ttk.Button(
            self.input_frame,
            text="Cancel",
            command=self.cancel_stream,
            state=tk.DISABLED
        )
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        
        self.input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Status Label
        self.status_label = ttk.Label(self.chat_frame, text="", foreground="gray")
        self.status_label.pack(pady=5)
        
        self.paned_window.add(self.chat_frame, weight=1)
    
    def setup_bindings(self):
        self.user_entry.bind("<Return>", lambda event: self.send_message())
    
    def handle_tab(self, event):
        self.code_editor.insert(tk.INSERT, "    ")
        return "break"

    def extract_code_blocks(self, text):
        # Find all Python code blocks in the text
        code_blocks = re.finditer(r'```(?:python)?\n(.*?)\n```', text, re.DOTALL)
        return [match.group(1).strip() for match in code_blocks]

    def create_new_tab(self, code_content=""):
        """Create a new tab with optional initial content"""
        # Create the main tab content
        tab = CodeTab(self.notebook)
        tab_id = str(uuid.uuid4())[:8]
        
        # Add the tab first
        self.notebook.add(tab, text=f"Code {tab_id}")
        
        # Create and add close button directly to the tab
        close_button = ttk.Button(
            tab,
            text="×",
            width=2,
            command=lambda: self.close_tab(tab),
            style='Tab.CloseButton.TButton'
        )
        close_button.place(relx=0.95, rely=0.01, anchor="ne")
        
        # Configure button style if not already configured
        style = ttk.Style()
        if 'Tab.CloseButton.TButton' not in style.theme_names():
            style.configure('Tab.CloseButton.TButton', 
                           padding=0,
                           relief='flat',
                           background='#0D1117')
        
        # Add Tab key binding to the code editor in this tab
        tab.code_editor.bind("<Tab>", self.handle_tab)
        
        if code_content:
            tab.code_editor.insert("1.0", code_content)
            tab.code_editor.highlight_syntax()
        
        self.notebook.select(tab)
        return tab

    def close_tab(self, tab):
        """Close the specified tab"""
        if self.notebook.index('end') > 1:  # Keep at least one tab
            self.notebook.forget(tab)
        else:
            messagebox.showinfo("Info", "Cannot close the last tab")

    def get_current_code(self):
        """Get code from the currently selected tab"""
        current_tab = self.notebook.select()
        if current_tab:
            tab = self.notebook.children[current_tab.split('.')[-1]]
            return tab.code_editor.get("1.0", tk.END).strip()
        return ""

    def send_message(self):
        if self.is_streaming:
            return
            
        user_input = self.user_entry.get().strip()
        code_content = self.get_current_code()  # Get code from current tab
        
        if not user_input:
            return
        
        self.start_time = time.time()
        
        # Combine user input and code if code exists
        combined_content = user_input
        if code_content:
            combined_content += f"\n\nCurrent code:\n```python\n{code_content}\n```"
        
        # Add user message and clear input
        self.chat_history.append({'role': 'user', 'content': combined_content})
        self.chat_window.insert(tk.END, f"You: {combined_content}\n\n")
        self.user_entry.delete(0, tk.END)
        
        # Update UI state
        self.toggle_ui_state(False)
        self.start_loading_animation()
        self.is_streaming = True
        self.current_response = ""
        
        # Start response thread
        threading.Thread(target=self.stream_model_response, args=(combined_content,)).start()
    
    def stream_model_response(self, combined_content):
        self.accumulated_response = ""  # Reset accumulated response
        
        try:
            stream = ollama.chat(
                model=self.model,
                messages=self.chat_history,
                stream=True
            )
            
            self.chat_window.insert(tk.END, "Assistant: ")
            for chunk in stream:
                if not self.is_streaming:
                    break
                chunk_content = chunk['message']['content']
                self.accumulated_response += chunk_content
                
                # Only update chat window during streaming
                self.chat_window.after(0, lambda c=chunk_content: self.update_chat_window(c))
            
        except Exception as e:
            self.chat_window.after(0, lambda: self.chat_window.insert(tk.END, f"Error: {e}\n"))
        
        finally:
            if self.is_streaming:
                elapsed_time = time.time() - self.start_time
                self.chat_history.append({'role': 'assistant', 'content': self.accumulated_response})
                self.chat_window.after(0, lambda: self.chat_window.insert(tk.END, f"\nElapsed time: {elapsed_time:.2f}s\n\n"))
                
                # Create tabs for code blocks after streaming is complete
                def create_code_tabs():
                    code_blocks = self.extract_code_from_response(self.accumulated_response)
                    seen_blocks = set()  # Track unique code blocks
                    for code_block in code_blocks:
                        # Only create tab for unique code blocks
                        if code_block not in seen_blocks:
                            seen_blocks.add(code_block)
                            self.create_new_tab(code_block)
                
                # Schedule tab creation after streaming
                self.chat_window.after(100, create_code_tabs)
            
            self.is_streaming = False
            self.chat_window.after(0, self.stop_loading_animation)
            self.chat_window.after(0, lambda: self.toggle_ui_state(True))

    def extract_code_from_response(self, text):
        """Extract all Python code blocks from the response."""
        # Look for code blocks with or without the python identifier
        patterns = [
            r'```python\n(.*?)\n```',  # Matches ```python\n code \n```
            r'```\n(.*?)\n```',        # Matches ```\n code \n```
            r'```(.*?)```'             # Matches ``` code ```
        ]
        
        code_blocks = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                code = match.group(1).strip()
                if code:  # Only add non-empty code blocks
                    code_blocks.append(code)
        
        return code_blocks
    
    def update_chat_window(self, chunk_content):
        self.chat_window.insert(tk.END, chunk_content)
        self.chat_window.see(tk.END)
        self.chat_window.update_idletasks()

    def update_code_editor(self, new_code):
        """Update the code editor with new code and highlight syntax"""
        # This method is no longer needed as we handle code blocks in stream_model_response
        pass

    def cancel_stream(self):
        """Cancel the current stream and process any code blocks received so far"""
        self.is_streaming = False
        
        # Process any code blocks that were received before canceling
        if self.accumulated_response:
            def create_code_tabs():
                code_blocks = self.extract_code_from_response(self.accumulated_response)
                seen_blocks = set()  # Track unique code blocks
                for code_block in code_blocks:
                    # Only create tab for unique code blocks
                    if code_block not in seen_blocks:
                        seen_blocks.add(code_block)
                        self.create_new_tab(code_block)
            
            # Schedule tab creation after a short delay
            self.chat_window.after(100, create_code_tabs)
        
        # Add a newline and elapsed time to the chat window
        elapsed_time = time.time() - self.start_time
        self.chat_window.insert(tk.END, f"\n[Stream cancelled] Elapsed time: {elapsed_time:.2f}s\n\n")
        self.chat_window.see(tk.END)
    
    def toggle_ui_state(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.user_entry.config(state=state)
        self.send_button.config(state=state)
        self.cancel_button.config(state=tk.NORMAL if not enabled else tk.DISABLED)
    
    def start_loading_animation(self):
        self.loading_dots = 0
        self.update_loading_animation()
    
    def update_loading_animation(self):
        if self.is_streaming:
            dots = "." * (self.loading_dots % 4)
            self.status_label.config(text=f"Model is responding{dots}")
            self.loading_dots += 1
            self.root.after(500, self.update_loading_animation)
    
    def stop_loading_animation(self):
        self.status_label.config(text="")

# [Rest of the code remains the same]

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatCodeEditor(root)
    root.mainloop()