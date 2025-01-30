import tkinter as tk
from tkinter import scrolledtext
import ollama
import threading
import time
import os

# Model ayarı
desiredModel = 'deepseek-r1:14b'

# Sohbet geçmişini ve thread kontrolü için değişkenler
chat_history = []
is_streaming = False
loading_dots = 0

# Mesaj gönderme fonksiyonu (threading ile)
def send_message():
    global is_streaming
    user_input = user_entry.get()
    if not user_input.strip():
        return
    
    start_time = time.time()
    
    # Kullanıcı mesajını ekle ve temizle
    chat_history.append({'role': 'user', 'content': user_input})
    chat_window.insert(tk.END, f"Sen: {user_input}\n")
    user_entry.delete(0, tk.END)

    # UI elemanlarını güncelle
    toggle_ui_state(False)
    start_loading_animation()
    is_streaming = True

    # Model yanıtını arka planda işle
    threading.Thread(target=stream_model_response, args=(user_input, start_time)).start()

# Model yanıtını akışla al (arka plan thread'inde)
def stream_model_response(user_input, start_time):
    global is_streaming
    model_response = ""
    output_file_path = "model_responses.txt"
    try:
        stream = ollama.chat(
            model=desiredModel,
            messages=chat_history,
            stream=True
        )

        for chunk in stream:
            if not is_streaming:
                break
            chunk_content = chunk['message']['content']
            model_response += chunk_content
            chat_window.after(0, lambda c=chunk_content: update_chat_window(c))

    except Exception as e:
        chat_window.after(0, lambda: chat_window.insert(tk.END, f"Hata: {e}\n"))
    
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        if is_streaming:
            chat_history.append({'role': 'assistant', 'content': model_response})
            chat_window.after(0, lambda: chat_window.insert(tk.END, f"\nGeçen süre: {elapsed_time:.2f}s\n\n"))

             # Write the model response to a file
            with open(output_file_path, "a", encoding="utf-8") as file:
                file.write("user input: \n")
                file.write(user_input + "\n")
                file.write(model_response + "\n")
                file.write(f"elapsed time: {elapsed_time:.2f}s\n")
        
        is_streaming = False
        chat_window.after(0, stop_loading_animation)
        chat_window.after(0, lambda: toggle_ui_state(True))

# İptal butonu fonksiyonu
def cancel_stream():
    global is_streaming
    is_streaming = False

def stop_loading_animation():
    loading_label.config(text="")

# Yükleme animasyonu
def start_loading_animation():
    global loading_dots
    loading_dots = 0
    update_loading_dots()

def update_loading_dots():
    global loading_dots
    if is_streaming:
        dots = "." * (loading_dots % 4)
        loading_label.config(text=f"Model yanıt veriyor{dots}")
        loading_dots += 1
        root.after(500, update_loading_dots)
    else:
        loading_label.config(text="")

# UI durumunu değiştir
def toggle_ui_state(enabled):
    state = tk.NORMAL if enabled else tk.DISABLED
    user_entry.config(state=state)
    send_button.config(state=state)
    cancel_button.config(state=tk.NORMAL if not enabled else tk.DISABLED)

# GUI'yi ana thread'de güncelle
def update_chat_window(chunk_content):
    chat_window.insert(tk.END, chunk_content)
    chat_window.yview(tk.END)
    chat_window.update_idletasks()

# Ana pencereyi oluştur
root = tk.Tk()
root.title("DeepSeek r1 Chat")

# Add/modify these grid configurations right after creating root window
root.grid_rowconfigure(0, weight=1)  # Chat window row
root.grid_columnconfigure(0, weight=1)  # First column (for user_entry)
root.grid_columnconfigure(1, weight=0)  # Send button column
root.grid_columnconfigure(2, weight=0)  # Cancel button column

# Modify the chat window grid


# Sohbet penceresi
chat_window = scrolledtext.ScrolledText(root, wrap=tk.WORD)
chat_window.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky='nsew')

# Kullanıcı girişi
user_entry = tk.Entry(root)
user_entry.grid(row=1, column=0, padx=10, pady=10, sticky='ew')

# Gönder butonu
send_button = tk.Button(root, text="Gönder", command=send_message)
send_button.grid(row=1, column=1, padx=5, pady=10)

# İptal butonu
cancel_button = tk.Button(root, text="İptal", command=cancel_stream, state=tk.DISABLED)
cancel_button.grid(row=1, column=2, padx=5, pady=10)

# Yükleme indikatörü
loading_label = tk.Label(root, text="", fg="gray")
loading_label.grid(row=2, column=0, columnspan=3, pady=5)

# Enter tuşu ile mesaj gönderme
user_entry.bind("<Return>", lambda event: send_message())

# Programı başlat
root.mainloop()