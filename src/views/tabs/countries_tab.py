from views.tabs import build_channel_groups


def build_countries_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, active_tiles):
    build_channel_groups(target, 0, page_obj, on_play, ad_service, liveliness, view_state, active_tiles)
