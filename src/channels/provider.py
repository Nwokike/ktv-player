import os
import importlib.util
from typing import List, Dict
from channels.base import ChannelData

class ChannelProvider:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.data_dir = data_dir
        self.modules = {}
        self._load_all_modules()

    def _load_all_modules(self):
        """Scan the data directory and load all .py modules."""
        print(f"Loading channel modules from {self.data_dir}...")
        for filename in os.listdir(self.data_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                file_path = os.path.join(self.data_dir, filename)
                
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                self.modules[module_name] = module
        print(f"Loaded {len(self.modules)} channel modules.")

    def get_all_channels(self) -> List[ChannelData]:
        all_channels = []
        for module in self.modules.values():
            all_channels.extend(getattr(module, "channels", []))
        return all_channels

    def get_channels_by_country(self) -> Dict[str, List[ChannelData]]:
        by_country = {}
        for module in self.modules.values():
            name = getattr(module, "group_name", "Unknown")
            channels = getattr(module, "channels", [])
            if channels:
                if name not in by_country:
                    by_country[name] = []
                by_country[name].extend(channels)
        return by_country

    def get_channels_by_category(self) -> Dict[str, List[ChannelData]]:
        # For simplicity, we use the 'group' field in ChannelData
        by_category = {}
        for channel in self.get_all_channels():
            cat = channel.group
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(channel)
        return by_category

    def get_countries(self) -> List[Dict[str, str]]:
        """Returns a list of country names and codes for the UI dropdown."""
        countries = []
        for module in self.modules.values():
            name = getattr(module, "group_name", "")
            code = getattr(module, "country_code", "")
            if name and code:
                countries.append({"name": name, "code": code})
        return sorted(countries, key=lambda x: x["name"])

# Shared instance
channel_provider = ChannelProvider()
