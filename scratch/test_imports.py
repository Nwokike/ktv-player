print("Importing flet...")
import flet as ft
print("Importing theme...")
from core.theme import AppTheme
print("Importing state...")
from core.state import state
print("Importing iptv_service...")
from services.iptv_service import iptv_service
print("Importing lifecycle...")
from services.lifecycle import LifecycleManager
print("Importing db_manager...")
from database.manager import db_manager
print("Importing SplashView...")
from views.splash import SplashView
print("Importing DashboardView...")
from views.dashboard import DashboardView
print("Importing PlayerView...")
from views.player_view import PlayerView
print("Importing OnboardingView...")
from views.onboarding import OnboardingView
print("All imports successful.")
