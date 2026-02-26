# ParanormaSprite

A desktop viewer for browsing and exporting character portraits from **PARANORMASIGHT: The Seven Mysteries of Honjo** (7MH) and **PARANORMASIGHT: The Mermaid's Curse** (TMC).

---

## Requirements

- A PC copy of 7MH and/or TMC (available on Steam)

---

## Installation

Download the latest `ParanormaSprite.exe` from the [Releases](../../releases) page. No installation is required — just run the exe.

A `cache/` folder will be created next to the exe the first time you extract sprites. This folder can be safely deleted to free up space; sprites will be re-extracted on demand.

---

## First launch

ParanormaSprite will attempt to automatically detect your PARANORMASIGHT installation(s) in the default Steam library location. If found, it will begin scanning for characters immediately.

If neither game is detected, or if your Steam library is in a non-default location, you will be prompted to locate the game folder manually. You can also add or remove game folders at any time using the **Add…** and **Remove** buttons in the **Game Folders** panel on the left.

> **Tip:** Select the top-level game folder (e.g. `…/steamapps/common/PARANORMASIGHT`), not a subfolder inside it. ParanormaSprite will find the right files automatically.

---

## Browsing portraits

1. Click **Scan** to populate the character list (this happens automatically on launch).
2. Click a character's name to load them. Characters that have already been extracted show a **✓** prefix.
3. The first time you select a character, their sprites are extracted from the game files and cached to disk. This takes a few seconds and only happens once per character.

---

## Controls

Once a character is loaded, the right-hand panel lets you compose a portrait:

| Control | Description |
|---|---|
| **Body** | The base pose (e.g. `base`, `side`, `back`, `dead`, `p0`–`p5`) |
| **Expression** | The expression core shared by the eye and mouth layers |
| **Eye frame** | The specific eye sprite variant |
| **Mouth frame** | The specific mouth sprite variant |
| **Reversed** | Flips the entire portrait horizontally, using alternate accessory layers for assymetric design elements |
| **Extra** | Adds optional overlay sprites on top of the portrait (e.g. blood, sweat) |
| **Blush** | Adds a blush layer (available on applicable poses) |

Controls that are not applicable to the current body pose are automatically disabled. Some features only exist on TMC sprites.

---

## Saving a portrait

Click **Save Portrait** to export the current view as a PNG.

---

## Rescanning

If you add a new game folder, click **Scan** to refresh the character list.

---

## Troubleshooting

**The character list is empty after scanning.**
Click **Scan** manually. A diagnostic message will appear describing what was found (or not found) in each game folder, which should help identify the issue.

**Extraction fails for a character.**
An error message will appear with details. Check that the game files are intact (try verifying them in Steam).

**The app doesn't find my game automatically.**
Use **Add…** to point ParanormaSprite to your 7MH or TMC installation folder directly.
