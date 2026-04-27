import flet as ft
try:
    d = ft.Dropdown(options=[ft.dropdown.Option("Test")])
    print("Dropdown with options created")
except Exception as e:
    print(f"Dropdown options error: {e}")
