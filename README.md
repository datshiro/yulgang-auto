# Yulang Mac Game Automation

Automation tool for **Yulang / Tái Chiến Võ Lâm** (native Mac App Store game in `Application/Games`).

Uses image recognition (OpenCV + PyAutoGUI) to simulate clicks for:

- **mở túi** – open bag/inventory
- **bán đồ nhanh** – quick sell items
- **hoàn thành nhiệm vụ** – complete quest
- **làm nhiệm vụ** – do quest
- **teleport to Huyen Bot** – use Huyền Bột teleport item

## Prerequisites

### macOS Accessibility Permission

PyAutoGUI needs Accessibility access to control the mouse. Add your terminal or IDE:

1. Open **System Settings → Privacy & Security → Accessibility**
2. Add **Terminal** (or Cursor, VS Code, etc.) to the list
3. Restart the terminal/IDE after granting permission

Without this, clicks will not work.

## Setup

```bash
cd yulangv2
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**Important:** Always activate the venv before running (`source venv/bin/activate`). Focus management (bringing the game to front, restoring your app) requires pyobjc, which must be installed in the same Python you use. If you run without the venv, you may see "pyobjc not available" warnings—the script will still try `open -b` as a fallback for bundle IDs.

## Template Images

Template images must be captured from the **Mac game** at your target resolution. Place them in `templates/`:

| Template | Purpose |
|----------|---------|
| `inventory_button.png` | Open bag |
| `quick_sell_button.png` | Quick sell button in inventory |
| `quick_sell_confirm_button.png` | Confirm sell |
| `close_button.png` | Close inventory after sell |
| `quest_button.png` | Open quest UI |
| `quest_accept_button.png` | Accept/start quest |
| `quest_complete_button.png` | Complete/claim quest |
| `huyen_bot_teleport_item.png` | Huyen Bot teleport item in inventory |
| `huyen_bot_teleport_text.png` | Verification text (Hồi Thành Phù Huyền Bột Phái) |
| `use_item_button.png` | Use item button (Dùng) |

**How to capture:**

1. Run the game in foreground
2. Use `screencapture` or crop screenshots
3. Save as PNG (40×40 to 80×80 px recommended)
4. Keep resolution consistent with how you run the game

## Usage

```bash
# Single actions (auto-activates game, runs, then restores your previous app)
python main.py --action open_inventory
python main.py --action quick_sell
python main.py --action complete_quest
python main.py --action do_quest
python main.py --action teleport_to_huyen_bot

# Loop mode (e.g. sell every 10 seconds)
python main.py --action quick_sell --loop --loop-interval 10

# Lower threshold if templates don't match (e.g. 0.65)
python main.py --action quick_sell --threshold 0.65

# Focus management (default: com.rxjhvn.iOS)
python main.py --action quick_sell --game-app "com.rxjhvn.iOS"
python main.py --action quick_sell --no-restore-focus   # keep game in front after

# Background capture: screenshot game without bringing to front; only activate for clicks
python main.py --action quick_sell --background-capture
```

### Finding the exact `--game-app` value

1. **Start the game** so it appears in the app list.
2. **Run the list script:**
   ```bash
   python scripts/list_apps.py
   ```
3. **Find your game** in the output (display name or bundle ID).
4. **Use it:**
   ```bash
   python main.py --action quick_sell --game-app "Exact Name Here"
   ```

To filter the list: `python scripts/list_apps.py --filter yulang`

**Note:** macOS cannot send clicks to background windows. The script brings the game to front, runs the automation, then restores your previous app (Terminal, browser, etc.) so you don't have to switch back manually.

## Project Structure

```
yulangv2/
├── core/           # Screen capture, template matching, click helpers
├── flows/          # Action flows (open_inventory, quick_sell, quests)
├── templates/      # UI template images (you capture these)
├── main.py         # CLI entry
└── requirements.txt
```

## Troubleshooting

- **Clicks don't work**: Ensure Accessibility permission is granted for Terminal/IDE
- **Templates not found**: Capture templates from the Mac game; emulator UI differs
- **Low confidence**: Lower `--threshold` (e.g. 0.65) or re-capture templates
- **Game updates**: UI changes may break templates; re-capture when needed
