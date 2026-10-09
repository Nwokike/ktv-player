# 12 — flet-ads 1.0.1 Deep Dive (REPORT ONLY — explain-then-ask)

Version: `flet_ads-1.0.1.dist-info/METADATA` → 1.0.1, requires flet==1.0.1.
Rule: NO ad-unit or consent code changes without explicit go.
Context: AdMob does NOT serve Android TV (GMA SDK constraint). Mobile serves AdMob.

## Inventory (installed source)

Ad types: Banner, Interstitial, Native ONLY. No Rewarded/RewardedInterstitial/AppOpen.

BaseAd (`base_ad.py`, @dataclass BaseControl): unit_id, request: AdRequest,
events on_load/on_error(e.data)/on_open/on_close/on_impression/on_click.
`before_update()` raises FletUnsupportedPlatformException if page.web or not
page.platform.is_mobile() — the TV enforcement.

BannerAd (`banner_ad.py`, @control("BannerAd"), LayoutControl+BaseAd):
adds on_will_dismiss (iOS), on_paid (allowlisted). Test IDs documented.

InterstitialAd (`interstitial_ad.py`, @control, Service+BaseAd): `async show()`.
Single-use contract: new instance per show; reuse errors.

NativeAd (`native_ad.py`, class NativeAd(BannerAd)): factory_id, template_style.
NOT exported from `__init__.__all__` — must `from flet_ads.native_ad import NativeAd`.
init() raises ValueError if both factory_id and template_style are None.

ConsentManager (`consent_manager.py`, Service, UMP): request_consent_info_update(params)
first every launch; is_consent_form_available(); get_consent_status();
can_request_ads() (the gate); get_privacy_options_requirement_status();
load_and_show_consent_form_if_required(); show_privacy_options_form() (only when
REQUIRED); reset() (testing only, never ship).

Types (`types.py`): AdRequest(keywords, content_url, neighboring_content_urls,
non_personalized_ads, http_timeout Android-only, extras); PaidAdEvent;
PrecisionType; NativeAdTemplateType/FontStyle/TextStyle/Style;
ConsentStatus NOT_REQUIRED/OBTAINED/REQUIRED/UNKNOWN (OBTAINED = decision collected,
NOT "granted" — use can_request_ads()); PrivacyOptionsRequirementStatus;
DebugGeography; ConsentDebugSettings; ConsentRequestParameters(tag_for_under_age...).

## Current usage (assessment: gating correct, events thin)

Mobile-only + premium + consent gating consistent across build_banner_ad, all
get_*_banner_ad, preload_interstitial, show_interstitial. UMP order correct
(request→load/show-if-required→can_request_ads at startup, skipped for premium).
Fail-open on UMP exception is deliberate logged policy. Interstitial lifecycle is
strongest part: preload, services keep-alive + release cleanup, 10s/30s/20s waits,
on-demand fallback, re-preload after close, bounded retry (5 x 30s), close cancel.
Single-use discipline respected. show_privacy_options status-guarded.

Gaps (utilization, not unit/consent correctness):
- Banners wire only on_error; on_load/impression/click/open/close/paid unused.
- Interstitial wires load/error/close only; open/impression/click/paid unused.
- AdRequest never customized (keywords/content_url/timeout/extras untouched).
- NATIVE_ID defined but NativeAd never instantiated; get_native_style_ad builds a
  BannerAd(300x250) with banner unit — misleading name + dead config.
- show_privacy_options has no UI caller (GDPR entry implemented, unwired).
- Banner errors only log; glass container stays as blank space (no collapse/reveal).
- Debug surface unused: test IDs, EEA geography, test_identifiers,
  is_consent_form_available/get_consent_status logging.

## Risks (report only)

- On-demand interstitial bypasses consent gate (preload checks _can_request_ads,
  show fallback checks only premium/mobile). Gate the fallback too.
- NativeAd import trap (not in __all__, needs factory/template + native setup).
- No Rewarded/AppOpen in this version — designs assuming them can't use it.
- on_paid allowlisted only; on_will_dismiss iOS-only.
- ConsentStatus.OBTAINED ≠ granted — code already respects via can_request_ads.
- Platform guard is an exception, not no-op — new ad/consent use needs is_mobile guard.
- Pin risk: flet-ads requires flet==1.0.1 but pyproject allows >=0.86.5.
- Interstitial-before-every-playback is product-frequency decision, no SDK capping.

## Additive opportunities (need go before any edit)

1. Wire banner on_load + on_impression; reveal on load, collapse on persistent error.
2. Wire interstitial on_open/impression/click (+paid if allowlisted).
3. Deliberate AdRequest choice (document defaults vs http_timeout/keywords/extras).
4. Debug path for QA (EEA geography + test IDs + status logging, dev only).
5. Wire show_privacy_options to Settings when status == REQUIRED.
6. Resolve native ambiguity (adopt real NativeAd with native verification, or remove
   NATIVE_ID and rename get_native_style_ad).
7. Fix _retry_task single-slot leak (track all pending or single-schedule flag).
