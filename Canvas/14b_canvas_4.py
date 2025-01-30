import tkinter as tk
from tkinter import scrolledtext, ttk
import ollama
import threading
import time
import os
from tkinter import font
import re

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
        # Remove all existing tags
        for tag in ["keyword", "string", "comment", "function", "number"]:
            self.tag_remove(tag, "1.0", "end")
            
        content = self.get("1.0", "end-1c")
        
        # Keywords
        keywords = ["def", "class", "import", "from", "return", "if", "else", "elif",
                   "try", "except", "finally", "for", "while", "in", "is", "None",
                   "True", "False", "and", "or", "not", "with", "as", "break",
                   "continue", "global", "lambda"]
        
        for keyword in keywords:
            start = "1.0"
            while True:
                start = self.search(r'\m' + keyword + r'\M', start, "end", regexp=True)
                if not start:
                    break
                end = f"{start}+{len(keyword)}c"
                self.tag_add("keyword", start, end)
                start = end
                
        # Strings
        pattern = r'(\".*?\"|\'.*?\')'
        for match in re.finditer(pattern, content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.tag_add("string", start, end)
            
        # Comments
        for match in re.finditer(r'#.*$', content, re.MULTILINE):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.tag_add("comment", start, end)
            
        # Functions
        for match in re.finditer(r'def\s+(\w+)\s*\(', content):
            start = f"1.0+{match.start(1)}c"
            end = f"1.0+{match.end(1)}c"
            self.tag_add("function", start, end)
            
        # Numbers
        for match in re.finditer(r'\b\d+\b', content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.tag_add("number", start, end)

class ChatCodeEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("DeepSeek Code Assistant")
        self.root.geometry("1400x800")
        
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
        
        # Code Editor Frame
        self.code_frame = ttk.Frame(self.paned_window)
        self.code_editor = SyntaxHighlightingText(
            self.code_frame,
            wrap=tk.NONE,
            font=('Consolas', 12),
            background='#0D1117',
            foreground='#C9D1D9',
            insertbackground='white'
        )
        self.code_editor.pack(expand=True, fill='both', padx=5, pady=5)
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
        self.code_editor.bind("<Tab>", self.handle_tab)
    
    def handle_tab(self, event):
        self.code_editor.insert(tk.INSERT, "    ")
        return "break"

    def extract_code_blocks(self, text):
        # Find all Python code blocks in the text
        code_blocks = re.finditer(r'```(?:python)?\n(.*?)\n```', text, re.DOTALL)
        return [match.group(1).strip() for match in code_blocks]

    def send_message(self):
        if self.is_streaming:
            return
            
        user_input = self.user_entry.get().strip()
        code_content = self.code_editor.get("1.0", tk.END).strip()
        
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
                self.accumulated_response += chunk_content  # Accumulate the response
                
                # Process the accumulated response for code blocks
                code_blocks = self.extract_code_from_response(self.accumulated_response)
                if code_blocks:
                    # Update the code editor with the latest complete code block
                    self.chat_window.after(0, lambda: self.update_code_editor(code_blocks[-1]))
                
                self.chat_window.after(0, lambda c=chunk_content: self.update_chat_window(c))
            
        except Exception as e:
            self.chat_window.after(0, lambda: self.chat_window.insert(tk.END, f"Error: {e}\n"))
        
        finally:
            if self.is_streaming:
                elapsed_time = time.time() - self.start_time
                self.chat_history.append({'role': 'assistant', 'content': self.accumulated_response})
                self.chat_window.after(0, lambda: self.chat_window.insert(tk.END, f"\nElapsed time: {elapsed_time:.2f}s\n\n"))
                
                # Final check for code blocks after response is complete
                code_blocks = self.extract_code_from_response(self.accumulated_response)
                if code_blocks:
                    self.chat_window.after(0, lambda: self.update_code_editor(code_blocks[-1]))
            
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
        """Update the code editor with new code and highlight syntax."""
        if new_code.strip():  # Only update if there's actual code
            self.code_editor.delete("1.0", tk.END)
            self.code_editor.insert(tk.END, new_code)
            self.code_editor.highlight_syntax()
            self.code_editor.see("1.0")  # Scroll to top

    def cancel_stream(self):
        self.is_streaming = False
    
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