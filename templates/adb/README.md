# ADB templates (BlueStacks / Android emulator)

Place template images here for use with `--mode adb`.

## High-accuracy template tips

1. **Capture via ADB** (not host screen):
   ```bash
   python scripts/adb_screenshot.py -o screenshots/reference.png
   ```
2. **Crop tightly** – include only the button/icon, minimal padding.
3. **Avoid variable content** – no timers, counters, or text that changes.
4. **Use PNG** – lossless; avoid JPEG compression artifacts.
5. **Debug match confidence**:
   ```bash
   python scripts/template_debug.py inventory_button.png -o debug.png
   ```
   Shows confidence at multiple scales; save highlighted image to verify.

**Copied from old yulang repo:** inventory_button, menu_button, attack_button,
auto_attack_button, auto_attack_cancel_button, che_tac_button, full_alert_text,
tach_action_button, tach_button, trang_ke_button.

**Quick sell:** `quick_sell_button.png`, `quick_sell_confirm_button.png`, and `close_button.png` live in this folder. `close_button.png` was copied from `templates/` so PyInstaller ADB-only bundles resolve it; **recapture from the emulator** if matching fails (resolution/UI may differ from Mac).

**For other flows:** go_to_npc_button, use_item_button, huyen_bot_teleport_item.png,
quest_button.png, quest_accept_button.png, quest_complete_button.png.

If a template is missing here, the code falls back to `templates/` (dev tree only). **Frozen `.app` bundles only `templates/adb/`**, so anything ADB flows need must exist under `templates/adb/`.
