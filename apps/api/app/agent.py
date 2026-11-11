import asyncio
import websockets
import urllib.request
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageWin
import win32ui
import win32print
from threading import Thread

# Configuration
SELLER_ID = "seller_123"
SERVER_URL = "ws://127.0.0.1:8000"
RECONNECT_DELAY = 5

class LodeLabelsAgent:
    def __init__(self, root):
        self.root = root
        self.root.title("LodeLabels Print Agent")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        
        self.websocket = None
        self.connected = False
        self.selected_printer = None
        
        self.setup_ui()
        self.load_printers()
        
        # Start WebSocket in background thread
        self.ws_thread = Thread(target=self.run_websocket_loop, daemon=True)
        self.ws_thread.start()
    
    def setup_ui(self):
        # Title
        title_label = tk.Label(self.root, text="LodeLabels Print Agent", font=("Arial", 16, "bold"))
        title_label.pack(pady=20)
        
        # Printer selection frame
        printer_frame = tk.Frame(self.root)
        printer_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(printer_frame, text="Select Printer:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        self.printer_var = tk.StringVar()
        self.printer_dropdown = ttk.Combobox(printer_frame, textvariable=self.printer_var, state="readonly", width=25)
        self.printer_dropdown.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Refresh button
        refresh_btn = tk.Button(self.root, text="🔄 Refresh Printers", command=self.load_printers)
        refresh_btn.pack(pady=5)
        
        # Status
        self.status_label = tk.Label(self.root, text="Status: Disconnected", fg="red", font=("Arial", 10))
        self.status_label.pack(pady=10)
        
        # Test print button
        test_btn = tk.Button(self.root, text="🖨️ Test Print", command=self.test_print)
        test_btn.pack(pady=5)
        
        # Info label
        info_label = tk.Label(self.root, text=f"Server: {SERVER_URL}\nSeller ID: {SELLER_ID}", 
                             font=("Arial", 8), fg="gray")
        info_label.pack(pady=10)
    
    def load_printers(self):
        """Load all available printers from Windows"""
        try:
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            printer_names = [p[2] for p in printers]
            
            self.printer_dropdown['values'] = printer_names
            
            if printer_names:
                # Select first printer by default
                self.printer_dropdown.current(0)
                self.selected_printer = printer_names[0]
                print(f"✅ Found {len(printer_names)} printers")
            else:
                messagebox.showwarning("No Printers", "No printers found on this system!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load printers: {e}")
    
    def update_status(self, status, color="black"):
        """Update the status label"""
        self.status_label.config(text=f"Status: {status}", fg=color)
    
    def test_print(self):
        """Print a test label"""
        if not self.selected_printer:
            messagebox.showwarning("No Printer", "Please select a printer first!")
            return
        
        # Create a simple test image
        test_image = Image.new("RGB", (406, 406), "white")  # 2x2 inches at 203 DPI
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(test_image)
        draw.text((50, 150), "TEST PRINT", fill="black")
        
        test_path = "test_label.png"
        test_image.save(test_path)
        
        success = self.print_label(test_path)
        
        if os.path.exists(test_path):
            os.remove(test_path)
        
        if success:
            messagebox.showinfo("Success", f"Test label printed to {self.selected_printer}")
        else:
            messagebox.showerror("Error", "Failed to print test label")
    
    def print_label(self, image_path: str):
        """Print a label to the selected printer"""
        try:
            # Update selected printer from dropdown
            self.selected_printer = self.printer_var.get()
            
            image = Image.open(image_path).convert("RGB")
            
            printer_dc = win32ui.CreateDC()
            printer_dc.CreatePrinterDC(self.selected_printer)
            
            target_width = round((image.width / 203) * printer_dc.GetDeviceCaps(88))
            target_height = round((image.height / 203) * printer_dc.GetDeviceCaps(90))
            
            dib = ImageWin.Dib(image)
            printer_dc.StartDoc("LodeLabels Agent")
            printer_dc.StartPage()
            
            dib.draw(printer_dc.GetHandleOutput(), (0, 0, target_width, target_height))
            
            printer_dc.EndPage()
            printer_dc.EndDoc()
            printer_dc.DeleteDC()
            
            print(f"🖨️ Printed {image_path} to {self.selected_printer}")
            return True
            
        except Exception as e:
            print(f"❌ Print error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def websocket_loop(self):
        """Main WebSocket connection loop with auto-reconnect"""
        uri = f"{SERVER_URL}/agent/ws/{SELLER_ID}"
        
        while True:
            try:
                self.update_status("Connecting...", "orange")
                print(f"Connecting to {uri}...")
                
                async with websockets.connect(uri) as ws:
                    self.websocket = ws
                    self.connected = True
                    self.update_status("Connected - Waiting for sales", "green")
                    print("✅ Connected!")
                    
                    async for message in ws:
                        data = json.loads(message)
                        
                        if data.get("type") == "print_job":
                            job_id = data["job_id"]
                            label_id = data["label_id"]
                            image_url = data["image_url"]
                            item_number = data.get("item_number", "?")
                            
                            print(f"📦 Received job {job_id} for Item {item_number}")
                            
                            # Download the PNG
                            local_path = f"temp_label_{label_id}.png"
                            urllib.request.urlretrieve(image_url, local_path)
                            
                            # Print it
                            success = self.print_label(local_path)
                            
                            # Acknowledge
                            status = "printed" if success else "failed"
                            await ws.send(json.dumps({
                                "type": "ack",
                                "job_id": job_id,
                                "status": status
                            }))
                            
                            # Clean up
                            if os.path.exists(local_path):
                                os.remove(local_path)
                                
            except (websockets.exceptions.ConnectionClosed, 
                    websockets.exceptions.ConnectionClosedError,
                    ConnectionRefusedError) as e:
                self.connected = False
                self.websocket = None
                self.update_status(f"Disconnected - Reconnecting...", "red")
                print(f"⚠️ Connection lost: {e}")
                await asyncio.sleep(RECONNECT_DELAY)
                
            except Exception as e:
                self.connected = False
                self.websocket = None
                self.update_status(f"Error - Retrying...", "red")
                print(f"❌ Unexpected error: {e}")
                await asyncio.sleep(RECONNECT_DELAY)
    
    def run_websocket_loop(self):
        """Run the async WebSocket loop in a separate thread"""
        asyncio.run(self.websocket_loop())

if __name__ == "__main__":
    root = tk.Tk()
    app = LodeLabelsAgent(root)
    root.mainloop()