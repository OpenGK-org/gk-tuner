# GK Tuner preview validation



Offline validation on 17 October 2026, Windows, Python 3.11, PyQt5.



**Current release: 0.13; 158 offline tests pass.** Distribution coverage verifies installed resource locations versus writable data, stale backend path recovery, explicit source/resource allowlists excluding private ECU dumps/XDFs/captures, and the logo to the left of the name. The frozen Windows x64 application passes startup, demo/map edit/undo, bundled ECU catalog, original GKFlasher checksum calculation, BSL/RSW asset paths, QtWebEngine, CCP sample/graphs, bundled libusb and palette bridge checks with Python removed from PATH. This is a local frozen-runtime check, not a clean-VM or physical hardware validation.

Version 0.12 coverage verifies scale-aware Flashing/Settings width limits, editable and persistent per-theme palettes, comparison endpoints, readable table text, table/3D palette propagation, invalid palette recovery and reset. The original GKFlasher checksum handler is exercised against a synthetic supported BIN: previewed old/new values, unsupported layout rejection, already-correct detection, Save/Cancel before correction, pending table commit, confirmation cancellation, undo/redo, corrected output save, and unchanged source bytes. Bounded forms, palette controls and custom heatmaps were rendered and inspected.

The actual Windows embedded CCP dashboard passed its interaction checks at 75/100/150/200% scaling at both 1440 x 900 and 1050 x 680, including custom palette propagation and reset, connection controls, mocked monitor/CSV start/stop, trace settings, graph cursor alignment, the blue time scrollbar, and CSV import/export. No hardware connections were made.

Version 0.9 coverage verifies multi-item clipboard ID/category preservation, linked-scale remapping across XDFs, effective storage defaults, invalid clipboard rejection, type-first creation/cancellation, both hexadecimal address forms, categorized name search, Header Apply saving without the removed actions, text editing/length/encoding/undo/comparison behavior, and navigation remaining open until toggled.

All eight text items from the actual expanded CA663056 XDF decoded in their dedicated editors. A text draft was accepted into the working BIN and undone; source XDF/BIN hashes stayed unchanged. Text editing, the X Axis scale picker and entry-only mismatch layout were rendered and visually checked.

 Version 0.8 verifies Save-table commit/close, selected-area +/- and numpad quantum changes, storage-bound rejection, raw hex display/edit/paste, comparison blocking, 64-bit patterns and endianness, uppercase map IDs 0x2CB2 and 0x53C5, byte-only mismatch filtering, forced-application confirmation/cancel/undo, and continued range/removal checks.

The actual expanded CA663056 XDF successfully loaded 0x2CB2 (4 x 1) and 0x53C5 (1 x 1) in the patch-map dialog. Editing the latter generated patch entries. A deliberate in-memory patch mismatch was blocked normally, force-applied, and undone to the exact pre-force bytes. Source XDF/BIN hashes stayed unchanged. Raw hex, mismatch-only patch layout, and the repaired actual map dialog were visually checked.

 Version 0.7 covers table-only draft Save, independent drafts, close Save/Discard/Cancel, conflict detection, changed-item color and active highlighting, BIN export versus pending drafts, direct XDF/header Save with unknown metadata preservation, category validation, item creation/removal, last-session restoration, atomic patch application/removal/undo, unsafe and missing-base cases, partial patches, patch properties/manual entries, and isolated map-to-patch generation with stride gaps preserved.

All four patches in the actual CA663056 XDF were checked against the source BIN in memory. Three reported matching base bytes; the Sirius/Sigma injector patch reported a compatible partially applied state. Each could be applied and undone back to the exact starting bytes. The source XDF/BIN hashes remained unchanged. Header, patch, patch-from-map, saved-map colors and active highlighting previews were rendered using disposable synthetic files.

 Version 0.6 verifies actual keyboard entry across a selection and a single Undo, invalid selection rejection, a visible separate graph window, graph lifecycle, rendering modes and theme colors, breakpoint/unit labels, bidirectional selection, point-drag preview and one-step commit/undo, downward dragging and graph keyboard undo/redo, invalid-drag/Esc cancellation, read-only comparisons, percentage gaps, and cancellation on external edits.



The real 0x18FC6 IVVT table was rendered with nine selected points, labeled Load (mg/stroke), Engine speed (RPM), and degrees. A graph drag changed the working binary, and one Undo restored all bytes. Source XDF/BIN SHA-256 hashes remained unchanged. Light, Dark, and wireframe screenshots were visually inspected.



 Version 0.5 checks separate file menus and unique icon images, successful recent-file loading without a file picker, failed-load preservation, six shared comparison slots, atomic multi-load/reload failures, reference replacement/unloading and reset on working-BIN load, mouse click versus double-click behavior, browser-order persistence/reset, and stable theme-specific workspace backgrounds, and refitting after scale changes settle. The new checks cover content fitting without scrollbars on a fitting table, thick-border resize events, top-positioned selection controls, graph toggle without tabs, direct internal-axis edits and undo/cancel/comparison blocking, refusal to write literal labels into the binary, constant staging/commit/undo/native-close cancellation, dedicated type inspectors, and overlay navigation animation. New coverage verifies that two editors are visible simultaneously without tiled-window overlap, native window close preserves binary edits, Compare changes both colors and state markers, appearance settings survive a settings reload, all five item types have distinct icons, heatmap text contrast exceeds 5:1 at sampled palette positions. Scaling was checked at 150%; the appearance preview is rendered at 125% with the Dark theme. No hardware operations were performed.



Version 0.2 adds regression coverage for multiple open tables, independent graph/selection state, all three comparison modes, undefined percentages, transactional properties, separate XDF saves, scoped equations, row/column-major and reversed/padded storage, and shared internal/linked axis edits. The complete offline suite contains 56 tests.



Version 0.4 was also checked against the expanded 360-item CA663056 XDF: two 16 x 12 IVVT tables and the 0x1011C constant rendered simultaneously in their respective editors. An X-axis linked breakpoint was changed in the working binary and undone, without opening an axis window. SHA-256 hashes confirmed both imported source files remained unchanged. No hardware was opened.



The user's 0x19571 IVVT map (16 rows × 12 columns) was opened from the actual CA663056 XDF and binary. Its General, Rows, Columns, Conversion, and DA association pages rendered successfully. Applying the property draft in memory validated correctly; the source XDF bytes and working binary remained unchanged. The row properties resolved Engine speed / RPM and the linked scale's first breakpoint (550).



- Automated regression suite: core binary edits and conversions, ADX parsing and fixed-frame transport, child-process prompts, and offscreen desktop workflows. Run `python -m unittest discover -s tests -v` to reproduce.

- Real XDF: `ca663056 2000.xdf` imports 253 items: 241 numeric maps and 8 inspection-only items and 4 overwrite patches.

- Real binary: read all 7,856 cells in those 241 maps from `ca663056_G7TCSP6C_KR77025241_KR77025160_2026-08-27_0310.bin`, including linked grid labels, with no decoding errors. This establishes parser coverage, not independent confirmation of every value against TunerPro.

- Real ADX: `lambda.adx` imports 102 numeric channel definitions. 81 are compatible with the implemented decoder and declared payload; 20 use linked equation variables and one field exceeds its declared payload. Unsupported channels are blocked from recording. Connect/monitor/disconnect macros expand to 12/3/2 supported steps.

- CAN backend loads 98 signal definitions and an idle Session without connecting a device.

- GKFlasher 1.0.99 CLI imports and prints help successfully. No identify, read, erase, or write operation was executed against hardware.

- K-line packet fixtures exercise fragmented reads, echo before header, parent routing, additive checksums, rejection of corrupted frames, cancellation, timeout, whole-session CSV capture, and disconnect cleanup using a fake serial port.

- GKFlasher console uses a harmless child-process fixture to verify live prompt detection and one response per prompt. The standard subprocess launcher is used because Qt5's process launcher exited silently on this machine.

- Five workspace previews are rendered to `artifacts/` with the Windows Segoe UI fonts registered for the offscreen renderer. Calibration, wireframe, and flashing previews were visually inspected.



No original ECU binary, XDF, ADX, logger source, or GKFlasher source was modified. Hardware and vehicle validation remain outstanding. Full TunerPro compatibility remains the development target described in COMPATIBILITY.md.

