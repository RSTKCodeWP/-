import tkinter as tk

root = tk.Tk()

root.title("UAV Touchscreen UI")
root.geometry("1024x600")

title = tk.Label(
    root,
    text="LoRa UAV Touchscreen UI",
    font=("Arial", 24, "bold")
)

title.pack(pady=20)

root.mainloop()