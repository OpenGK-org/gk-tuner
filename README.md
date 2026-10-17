# GK Tuner

Windows test releases are built in release/0.13.0. Use GK-Tuner-0.13.0-Setup-x64.exe for a per-user installation with Start menu and optional desktop shortcuts, or extract the complete Portable-x64.zip. Python, Qt, CAN logger and GKFlasher are included. Windows adapter drivers remain separate. Uninstall preserves user settings, captures and external BIN/XDF files. This preview is unsigned.

The logo sits to the left of the GK Tuner name. Installed builds store writable data under %LOCALAPPDATA%/GK Tuner, separate from the program files. Source/build instructions are in packaging/README.md; third-party notices and exact runtime versions are included in the release. The commands below describe running from source.


Flashing and Settings use bounded, scale-aware layouts. In Program properties, Colours > Edit palette changes the interface, working heatmap and comparison heatmap independently for Light and Dark themes. Changes apply immediately and persist; Reset this theme restores its defaults. Table text adjusts to heatmap brightness; the 3D view and embedded CCP dashboard follow the chosen colours. Per-trace logger colours stay independent.

The top toolbar checksum icon and File > Correct BIN checksum use the original GKFlasher checksum handler on a temporary copy of the currently loaded BIN. Unsaved table/BIN edits require saving first. Confirmation lists each current and proposed checksum; accepting updates the working BIN as one undoable change. Use Save BIN to write the corrected file. Unsupported layouts and images with no checksum regions are reported without modifying the BIN. An already-correct checksum is reported without creating an edit.




Native Windows tuning workspace, built with Python and Qt. Version 0.13 shows multiple definition items simultaneously in movable, resizable windows, with a higher-contrast interface, persistent UI scaling, distinct comparison colors, and type-specific icons.



## Start



Double-click **start_gk_tuner.bat**, or run:



```powershell

python -m gktuner

```



Python 3.11, PyQt5 and PyQtWebEngine are already available on the development machine. On another machine install `requirements.txt`. The existing logger and GKFlasher each retain their own dependency requirements; configure their folders in Settings.



## Calibration workflow



1. Open a binary and import its matching XDF.

2. Search or expand a category and double-click an item. Gray entries marked with a circle are inspection-only; their reason appears above the editor.

3. Edit individual cells or select a range and type a number to set every selected cell at once. Selection entry is one undoable, atomic change; invalid values leave every cell unchanged. You can also select a range and apply an operation. Ctrl+C / Ctrl+V copy and paste tab-separated cells. Ctrl+Z / Ctrl+Y undo and redo whole operations.

4. Open a same-size comparison binary and hover cells for differences.

5. Press each table's Save icon to accept its draft into the working BIN, then use Save BIN as to write a new file. Source binaries are protected against in-place saves. Validate ECU compatibility and checksums before writing an ECU.



File contains BIN commands and Recent BINs; XDF contains definition commands and Recent XDFs. Each history keeps the last ten successfully opened or saved paths. BIN icons use 010; XDF icons use DEF, with folders for loading and disk shapes for saving. Undo/Redo use curved arrows.



Categories start collapsed and have folder icons. Categories follow XDF header order; items follow their order in the XDF. Single-click selects; double-click opens. Right-click provides Properties without opening an editor. Drag items within a category or drag categories to reorder them. Custom browser order is saved per imported XDF without modifying its contents. Dragging is disabled during a search. Constants, tables, functions, patches, and flags/switches have different icons and type tooltips. Double-clicking additional items opens separate windows in the same workspace, so they remain visible at the same time. The top icon toolbar provides Tile, Side by side, Cascade, Fit to data, and Auto arrange. Windows fit their data instead of stretching to fill unused space; large tables scroll when they exceed the workspace. Drag the thicker window borders to resize manually; this turns off Auto arrange. GK Tuner navigation slides in from the left and pushes the workspace aside. Click a page to navigate and close the menu, including the current page; the menu button also toggles it. The supplied OpenGK SVG sits to the left of the Trebuchet MS wordmark and is used as the application icon. Each icon has a tooltip.



The per-table toolbar provides Save, Close, Show 3D Graph, Compare, comparison settings, Edit X axis, Edit Y axis, and Properties. The toolbar includes a 0x toggle for zero-padded raw hexadecimal storage values without conversion. Raw typing and paste edit the stored pattern directly; converted comparison and batch-operation controls are disabled in this view. Toggling back restores converted values. With the table focused, + and - (including numpad keys) raise/lower every selected cell by one stored count, independent of conversion. A selection is changed as one undoable draft edit; storage overflow rejects the whole adjustment without wrapping. These raw operations bypass engineering conversion/ranges while retaining storage bounds. The toolbar uses compact icons with tooltips: a 3D mesh, two comparison sheets, and X/Y axis letters. Selection operations appear directly below it, above the data. The table Save icon accepts only that table's draft into the working BIN and closes its editor (including its linked graph). It never opens a BIN file-save dialog. Closing a table with unsaved edits offers Save, Discard, or Cancel; Discard leaves the working BIN unchanged. Separate tables have independent drafts, including their axis and graph edits. Saved changes color the corresponding item red in Light theme or salmon in Dark theme, relative to the loaded source BIN; activating an editor highlights its item. Overlapping drafts are checked against their original bytes before a merge, preventing accidental overwrites. BIN Save resolves pending drafts and writes the accepted working bytes to a file.



The Compare toolbar dropdown -> Load compare BINs (Ctrl+F1) loads up to six same-size reference binaries into global slots. Ctrl+1 through Ctrl+6 selects a slot; every open comparison view uses that active reference. Hover a BIN slot to select it or access Load/replace, Reload from disk, and Unload. The toolbar dropdown is the single Compare menu. Multi-file loading replaces slots 1 onward and leaves higher slots intact; validation completes before any slot changes. Loading a new working BIN clears the reference slots. Table Compare buttons toggle the comparison view; Absolute/Difference/Percentage remain separate per table. Absolute shows reference values, Difference shows working minus reference, and Percentage shows that difference relative to the reference. Zero references produce a dash in percentage mode. Comparison views are read-only, with a violet/lavender/amber heatmap, a COMPARE banner, and a window-title marker. Working values use cyan/cream/coral with dark, high-contrast text. The workspace background remains the same with zero or multiple editors, using separate Light and Dark colors.



Open **Program â†’ Program propertiesâ€¦** (or Settings) to choose Light or Dark and an interface scale from 75% to 200%. Apply appearance changes fonts, controls, table rows, and icons immediately and saves the preference for the next launch. The scale is applied on top of the system's DPI setting and does not change binary values.



Open Properties from the table toolbar or by right-clicking a map in the browser. General, Rows, Columns, Conversion, and DA association tabs edit the supported definition fields. Edit X/Y axis opens a linked scale or internal axis as a data table; literal labels open the corresponding Properties tab. Double-click a grid axis header to change a linked or internal breakpoint directly in the working binary, without opening another editor. Shared axis edits refresh every open map that uses that scale and support Undo. Literal XDF labels have no binary address and must be changed in Properties. Comparison headers are read-only.



Properties alter the working XDF independently from binary edits. Apply/OK validates changes; Cancel discards unapplied changes. Use **Save XDF asâ€¦** to persist properties in a new definition file. Save XDF writes the current definition in place; Save XDF as writes a separate file. Global and scoped row/column/cell equations support arithmetic in X; nonlinear conversions remain view-only. Visibility and DA association values are metadata for future filtering and live tracing.



Tables have no view tabs. Show 3D Graph opens a separate window, keeping the table visible. Choose Heatmap + mesh, Filled heatmap, or Wireframe; the graph follows the Light/Dark theme and the table heatmap. X/Y axes show actual XDF breakpoints and units; Z shows values and units, or percentage/difference when comparing. Yellow markers track table selections. Click a point to select it, Ctrl-click to toggle selection, and drag a selected point up/down to adjust the whole selection. The drag is a preview until release and commits as one undoable table-draft operation, with storage quantization and XDF limit checks. Esc cancels; an out-of-range release cancels the adjustment. Drag empty space (or right-drag) to rotate, scroll to zoom, and use Reset view to restore orientation. Ctrl+Z/Ctrl+Y work inside the graph. Comparison graphs remain read-only. Closing a table also closes its graph. Constants (including single-value tables) have a compact numeric editor with a slider when a usable range exists, comparison value, Copy reference, Save, and Cancel. Constant Save applies the draft to the working binary; Save BIN as writes a file. Closing a pending constant offers Save/Discard/Cancel. Text output (type 4, 8-bit character storage) has a dedicated editable single-byte text field, including VIN, serial and version fields. Text edits remain a table draft until Save, with fixed storage length, explicit 00/space padding and Undo. Functions and flags/switches have dedicated inspection windows; their write adapters are still pending. Patches have an editable overwrite workflow described below. Select **File â†’ Open demonstration** for a synthetic ignition map that can be edited without using vehicle files.



## XDF management and patches

Select items in the browser and use Ctrl+C/Ctrl+V or its Copy/Paste context actions. Multiple items can be selected with Ctrl/Shift. Copies get new IDs and a Copy of title; BIN contents are unchanged. Clipboard copies preserve XML metadata, categories and effective storage defaults. Linked scales stay shared within the same XDF; copying across XDFs also brings referenced scale definitions with remapped links.

Linked scale selection in Rows/Columns opens a name search and a category tree. Browse X Axis/Y Axis or filter by part of a map name, then select the scale. Address fields accept both prefixed and bare hexadecimal, for example 0x1A0 and 1A0.


Use XDF -> Add new item, choose a type, then enter its details in Properties. The first window contains only the item type. No item is added if you cancel before applying. New items use the header defaults; Properties edits the supported storage, units and conversion fields. Remove item is available in the XDF menu and browser context menu. Removing a definition leaves BIN bytes unchanged; referenced axis scales must be unlinked first.

XDF -> Edit XDF header edits title, description, author, version, base offset, BIN region size, new-item defaults and categories. Advanced XML preserves and permits editing other header metadata, including checksums, sync groups and DA information; it does not execute checksum calculations or encryption. Header Apply validates the edits and saves the current XDF file. The separate Save XDF header button has been removed. Save XDF as remains available in the XDF menu.

A patch window reports the working BIN state and the selected comparison BIN state. Apply patch / Remove patch change the working BIN as one undoable operation; Save BIN writes the result to disk. Expected base bytes and patch bytes are checked entry by entry before any mutation. Normal Apply blocks the entire patch on a mismatch. The mismatch list shows only affected entry names and their start addresses; individual differing bytes are not expanded. Force apply is available for conflicting data after an explicit warning, defaulting to No. It still validates addresses, sizes and overlapping entries. Undo restores the exact pre-force bytes; Remove patch restores declared base bytes, which may be different. Matching partially applied patches can be completed safely. Entries without base data require explicit unverified-application confirmation and cannot be removed automatically without original bytes.

Edit patch provides title, description, visibility, categories and entry creation/edit/deletion. Each overwrite entry has a name, address, patch bytes, computed byte size and optional base bytes. From XDF map supports mixed-case XDF IDs and opens an isolated map copy: edit its values and Save to generate entries with original base bytes and changed map data. Noncontiguous map storage becomes multiple entries; stride gaps are preserved. Saving a patch definition changes only the working XDF until Save XDF is used.

The program restores the last BIN/XDF file paths, open item windows, active item, window arrangement, browser width, main-window geometry and selected page at startup. Theme, scale, recent files and custom item order also persist. Only saved files are reopened; table/BIN close prompts resolve unsaved changes before exit. Focus workspace has been removed.

## CAN logging



Logging embeds the existing CCP logger's complete dashboard: searchable signals, DAQ capacity, connection settings, Record to CSV and Live monitor, sample/CSV import, duration/sample/rate metrics, live values, up to eight configurable traces, per-signal colors and Y limits, zoom, time scrolling, cursor inspection, graph resizing and CSV export. CSV log / Live monitor, Start/Stop and Connection settings are at the top of the logger sidebar. Connection settings shows adapter channel, CAN bitrate and DAQ rate by default; its heading can collapse the inputs. The dashboard follows the program theme and scaling, and retains signal/trace preferences.

The backend is the sibling `ECU Reverse Engineering/ca663056 CCP/Logger/ccp_studio.py`. Its Session, signal definitions (including the boost controller), decoders, acquisition planning and CSV writer are reused. QWebChannel connects the dashboard directly to GK Tuner's shared capture session without an HTTP server. CAN, K-line and GKFlasher cannot acquire the adapter concurrently. Opening Logging loads sample data and metadata only; Start capture/monitor opens the adapter. Full recordings remain in the existing logger's Logs folder.



## Flashing



The Flashing & ECU tools page defaults to **K-Line**. Connection settings provide an editable/refreshable adapter selector, automatic or manual ECU selection, and the diagnostic-session speeds from GKFlasher's own ECU catalog. CAN disables the K-Line speed choice. Settings persist between sessions.

- **Read / Write:** calibration, program and full reads; calibration, program and full writes; identification and adaptive-value clearing.
- **File tools:** checksum correction to an output copy, BIN-to-SIE and SIE-to-BIN conversion. Existing files and source inputs are preserved. GKFlasher reviews calculated checksums before saving them.
- **Diagnostics:** ECU identification, DTCs, adaptive values, VIN reading and writing.
- **Immobilizer:** status, reset, SMARTRA neutralization, key teaching, limp-home activation/password changes and the VIN-to-PIN calculator. The original GKFlasher input dialogs and handlers are reused.
- **Recovery:** RSW boot software, application, calibration, full image and virginization; BSL hardware information, internal-ROM/external-flash reads and external-flash writes, with bootstrap speed, read size and flash-layout choices. RSW requires CAN. This installed handler writes Boot1/Boot2 together; separate CLI Boot1/Boot2 flags have no implemented handler. BSL uses its own automatic bench-adapter detection.
- **Advanced:** a custom read address range, MTOS payload/key and the original KWP logger. MTOS is experimental. Stop monitor interrupts only the long-running KWP/MTOS sessions; flash writes cannot be interrupted by that button. The legacy logger writes log.csv and refuses to replace an existing capture.

GK Tuner binds the existing `GKFlasher-1.99 STOCK/gui.py` handlers to its own widgets and directly calls its BSL, memory, checksum, conversion and recovery modules. Its flash algorithms and protocol code are not copied or modified. Startup skips standalone window/working-directory setup. Background jobs route logs/progress into the page, retain exclusive adapter ownership through PIN/VIN prompts, and release resources on completion or errors. Opening this page does not open a connection. Physical ECU operations have not been performed during development.



## K-line logging



Import an ADX in Logging. Supported numeric channels can be selected in K-line mode; unsupported channels are gray with a reason. Use **Review ADX transport** to inspect the connect/monitor/disconnect command plan, enter the serial adapter port (for example COM3), and start recording to a new CSV. Start recording executes the imported commands. ADX support covers a bounded fixed-frame subset, with compatibility checks before the port opens. Baud and initialization commands come from the ADX. Receive checksum verification is an explicit option for frames with a trailing additive checksum.



This adapter is experimental: packet-fixture tests pass, but no vehicle or physical adapter has been used for validation. Confirm initialization timing and framing against captured replies before relying on it for tuning.



## Status and validation



Read [COMPATIBILITY.md](COMPATIBILITY.md) for the exact supported subset and remaining work toward TunerPro parity. **This is a desktop preview, with experimental K-line logging. Live tuning remains planned.** Map Editor saves do not recalculate checksums; use Flashing -> File tools -> Correct checksum to create a corrected copy through GKFlasher.



Run the offline regression suite:



```powershell

python -m unittest discover -s tests -v

```



No hardware access is required by these tests. Existing backends are referenced rather than vendored; their licenses and attribution remain with their source projects. GKFlasher's source tree includes its GPL license. Distribution of a bundled application needs a deliberate licensing decision before release.


The complete embedded logger UI can be verified on Windows with `python -m tools.verify_logger_ui`. It checks sample data, filtering, trace settings, zoom/fit, Light/Dark rendering and CSV import/export without opening hardware.

Logger UI checks send real mouse events to the embedded browser at 75%, 100%, 150% and 200% scaling, at 1440×900 and 1050×680. They check visible capture controls, connection inputs, the gear dialog and pointer/marker alignment. Start/Stop checks mock capture so no adapter opens. The time slider has an explicit blue track and circular handle for Qt’s browser.

The logger applies the program scale after attaching its browser page and reapplies it after page loads, so saved scaling also works on first opening and reload. Startup checks include a saved 150% scale.

Run `python -m tools.render_flashing_preview` to render all Flashing sections in both themes without loading the hardware backend.
