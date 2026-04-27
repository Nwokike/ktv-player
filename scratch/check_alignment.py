import flet as ft
print(f"Page methods: {[n for n in dir(ft.Page) if 'route' in n or 'go' in n]}")
