# GK Tuner 0.12 — compatibility and development plan

Program properties provides persistent per-theme UI, working-heatmap and comparison-heatmap palettes, shared with the 3D graph and embedded CCP dashboard. Flashing and Settings have scale-aware width limits.

Map Editor checksum correction is available from the top toolbar and File menu. It calls GKFlasher's original checksum handler on a temporary copy, previews current/proposed values, then applies an accepted correction as an undoable working-BIN edit. Saving the corrected file remains a separate BIN Save operation. Supported layouts are those recognized by the configured GKFlasher source.




This is the first working desktop preview, not full TunerPro parity. No ECU or adapter is connected automatically. Hardware behavior has not been validated on a vehicle.



## Available now



- Import XML XDF definitions, browse categories, search titles and addresses, and inspect the original XML for every item.

- Map Editor with collapsed folder categories and multiple movable/resizable item windows visible simultaneously. Tile, Side by side, Cascade, and Auto tile control the layout. Constants, tables, functions, patches, and flags/switches use distinct icons; unsupported types retain their original XML for inspection. Each table has Save, Close, Show 3D Graph, Compare, comparison settings, X/Y axis editing, and Properties, with selection operations above the data and no view tabs. Content-sized windows have thicker resize borders. Commands use a top icon toolbar; navigation slides in, pushes the workspace aside and closes on selection, with the supplied OpenGK branding/icon. Constants have dedicated numeric editors with staged Save/Cancel and reference copying. Functions and flags have separate inspection windows; patches have dedicated state, application and entry-editing windows. Table edits are independent drafts. Save table merges only that draft into the working BIN with expected-byte conflict checks and closes the editor. Closing a pending table offers Save/Discard/Cancel; BIN Save writes accepted data to disk. Saved user changes color items, and activating a window highlights its item.

- Light and Dark themes, readable working heatmaps with dark text, and a visually distinct violet/lavender/amber comparison palette. Comparison windows carry a COMPARE banner and title marker. Program properties offers saved 75–200% interface scaling, applied immediately on top of system DPI without changing calibration values.

- Item properties: title, description, storage address and computed file address, cell size, signed/LSB/floating flags, row/column order, byte strides, range limits, visibility level metadata, output type, decimal places, units, and three category memberships. Rows and Columns tabs edit counts, literal labels, linked scales, internal axis storage, units, and type metadata. Conversion supports global and scoped row/column/cell equations. DA association indices can be stored; map tracing remains planned.

- Apply/OK validates a private property draft before replacing the working definition. Cancel discards unapplied property edits. Save XDF as… writes a separate definition, preserving unknown XML nodes and attributes; Save XDF writes the current definition in place; Save XDF as creates a new file. XDF edits do not alter binary bytes.

- Open binary images without changing their source files. Save edited images under a different name using an atomic file replacement.

- Numeric tables and constants with 8/16/32/64-bit integers, signed storage, little/big endian, and 32/64-bit IEEE floating point.

- Packed row/column-major storage and byte-aligned strides, including reversed element/line order. Overlapping storage is inspection-only. Explicit base offsets. Common arithmetic equations using X, numbers, parentheses, +, -, *, and /.

- Affine conversion back to stored values, storage overflow checks, XDF min/max checks, and transactional batch changes. Nonlinear arithmetic equations are view-only.

- Heat-colored table and a separate themed 3D window with filled heatmap, mesh, and wireframe modes, drag rotation, and scroll zoom. Plot axes display actual XDF breakpoint labels, units, and value ticks (breakpoints are uniformly spaced by table position). Table selections appear as graph markers; dragging a selected point previews a shared engineering-value adjustment and applies it to the table draft on release, as one undo step. XDF/storage limits, read-only comparisons, cancel, and concurrent document changes are checked before committing. Each graph closes with its table. Linked XDF table axes and literal labels appear in the grid; unresolved axis values are marked with # indices. Double-click linked/internal axis headers to update the working binary with shared-map refresh and undo; literal labels stay in the XDF.

- Undo/redo, typed values applied atomically across the selected cells, rectangle copy/paste, set/add/multiply/percentage operations, row/column interpolation, and map CSV export. Changed bytes highlight affected cells.

- Six same-size comparison BIN slots selected globally from the Compare menu, with individual replace/reload/unload and Ctrl+1 through Ctrl+6 shortcuts. Selection refreshes all open comparison views. Each table has a separate display mode: Absolute displays reference values; Difference displays working minus reference; Percentage displays (working minus reference) / reference × 100. Undefined percentages show a dash. Comparison views are read-only; turn Compare off to edit the working map. Hover over cells for raw, working, reference, equation, and difference values.

- The existing CCP logger's full dashboard is embedded with QtWebEngine: sample and CSV sources, 103 CAN/CCP signal definitions including boost controller broadcasts, signal search/defaults, DAQ capacity and connection settings, Record/Live monitor, live values, metrics, up to eight configurable traces, colors and Y limits, zoom/time scrolling/cursor inspection, resizing and CSV export. QWebChannel reuses the actual Session and decoders without an HTTP server. Signal and trace preferences persist in GK Tuner settings; themes/scaling follow the program. Capture shares adapter ownership with K-line and GKFlasher. Physical CAN acquisition remains unverified in GK Tuner.

- GKFlasher UI integration reuses the original GUI handlers and modules: K-Line by default, adapter refresh/edit, manual/automatic ECU selection, session speed, calibration/program/full reads and writes, address-range reads, checksum correction to a copy, BIN/SIE conversion, diagnostics, adaptive values, VIN and immobilizer tools, BSL, RSW, MTOS and the legacy KWP logger. Output/progress and existing input dialogs are integrated. Long-running monitor sessions can be stopped; writes cannot be interrupted by that control. CAN logging, K-line logging and GKFlasher share adapter ownership exclusively. The app cannot close while an operation or its input prompts remain active. Backend source files are not changed.

- ADX XML import: channel names, sizes, offsets, parent-command references, equations, and complete commands/macros for inspection.

- Experimental K-line acquisition through pyserial: bounded send/listen/fixed-delay/macros, per-command baud changes, additive send checksums, synchronization headers, partial-read assembly, echo skipping, parent-packet routing, numeric channel conversion, CSV capture, cancellation, and disconnect cleanup. Unsupported commands, cycles, invalid lengths, missing parent packets, and out-of-payload fields are rejected before opening a device.



- Separate BIN/XDF menus, persistent recent-file lists, and distinct 010/DEF load/save icons. Items open on double-click. Browser order follows the XDF by default; drag ordering within categories and category reordering persist per definition, with persistent drag ordering. Reordering affects the browser only. The empty and populated workspaces share a stable background, chosen separately for Light and Dark.



- XDF header and category editing, item add/remove, direct XDF Save and Save as, and last-session file/window arrangement restoration.
- Overwrite patch application/removal with atomic expected-byte checks, partial-state detection, comparison state, undo/redo, manual entry editing and map-derived entries preserving stride gaps. Missing base bytes require explicit unverified application. Normal Apply blocks mismatches; Force apply can override them after a warning while retaining range/size/overlap checks. Removal requires complete base bytes. Only affected entry names and start addresses appear in the mismatch list. Other patch operations remain unsupported.

- Raw hexadecimal table view/edit/paste bypasses conversion. Keyboard + and - including numpad adjust selected storage patterns by one count, atomically and without wrapping. Engineering conversion/range limits are bypassed for raw operations; storage bounds remain enforced. Converted comparison/batch controls are disabled while raw view is active. Raw display preference persists per reopened table.

- Browser item copy/paste with fresh IDs, category/default preservation and linked-scale dependency handling; type-first creation with a private Properties draft; prefixed/bare hexadecimal addresses; searchable categorized scale selection. Header Apply saves the current XDF. Order-reset commands and hover navigation are removed; the animated navigation drawer is toggled only by its button.
- Editable type-4 text in 8-bit single-byte storage, including VIN/serial/version fields, with length and encoding checks, padding, staged Save/Discard and Undo. Wider text storage remains unsupported.

## Explicit limits



- XDF flags, functions, custom variables, custom equation functions, bit strides, plugins, and checksum modules are inspection-only or unsupported. They are not silently converted to writable numeric maps. Global/row/column/cell equations support arithmetic in X; conflicting row and column scopes require an explicit cell equation.

- Importing an XDF does not establish that it matches a binary or ECU. No automatic firmware matching exists yet.

- Binary exports do **not** recalculate checksums. Validate the saved image with the appropriate ECU-specific checksum implementation before flashing. GKFlasher retains its own validation behavior.

- Properties edit the supported XDF subset; unsupported item storage/conversions remain read-only. Visibility levels and DA indices are stored as metadata; visibility filtering and live tracing remain planned. Only known data-type/stock-unit IDs have friendly names; other IDs are preserved and can be entered numerically. An ADX definition editor is not implemented.

- K-line acquisition supports a fixed-frame ADX subset, not all ADX features. The imported connect/monitor/disconnect commands are sent only after Start recording. Review ADX transport lists the commands that will execute. Linked equation variables, bitmasks, lookup channels, dynamic-length frames, adaptive silence detection, checksum options other than whole-command additive send checksums, and custom FTDI initialization are not supported. Gray channels remain available for inspection.

- K-line receive checksum verification is optional and explicitly selected: use it only for a whole frame whose last body byte is an 8-bit additive checksum. The ADX header/body/payload lengths are used exactly as defined; the app does not infer ECU framing or change imported offsets. Compatibility checks and packet-fixture tests do not establish that a definition matches a vehicle. Serial fast-init timing and hardware behavior remain unvalidated.

- CSV logs can be opened to inspect the final sample. Timeline playback, charting, synchronized map tracing, histograms, and automatic correction suggestions remain planned.

- GKFlasher handlers load from its existing source folder with its own dependencies and configuration. RSW Boot1 and Boot2 are supported together as boot software; this installed handler does not implement the separate Boot1/Boot2 CLI flags. MTOS retains the backend�s experimental status. Its erase/write algorithms are not copied or changed. Hardware operations have not been executed as part of development.

- GUI controls and processes inside GK Tuner share adapter ownership. Separate external applications can still open hardware; close those applications before connecting.

- Windows installer, code signing, and standalone bundled executable remain planned. Run the included launcher with the existing Python installation.



## Required milestones toward the requested application



1. **Compatibility core:** broaden fixture coverage; validate storage behavior and base-offset conventions against known TunerPro exports; implement flags, switches, additional patch operations, functions, full equations, broader definition editing, and checksum extension interfaces.

2. **K-line logging:** expand the implemented fixed-frame macro interpreter with linked channels, more checksum algorithms, dynamic framing, and FTDI transports; perform bench validation against the user's lambda.adx and captured ECU replies.

3. **Logging workspace:** time-series charts, playback, channel presets, CAN boost channels, map tracing, cursor inspection, histograms, and session export.

4. **Flashing workflow:** bench-test each supported ECU/protocol combination, then add backup manifests and ECU-specific recovery guidance. Structured progress and the existing checksum/ECU handlers are integrated.

5. **Desktop release:** project sessions, recent files, favorites, keyboard/accessibility review, installer, and signed executable.

6. **Future live tuning:** validated ECU-specific RAM/calibration transport, checks before applying changes, rollback, session audit, and strict separation from offline editing.



Reference scope: [TunerPro calibration overview](https://www.tunerpro.net/WebHelp/source/tunerprooverview.htm), [TunerPro data acquisition overview](https://www.tunerpro.net/WebHelp/source/dataacq.htm).



Storage reference: the [UniversalPatcher author's XDF stride investigation](https://github.com/joukoy/UniversalPatcher/pull/14) documents element-step, line-gap, column-major, and reversal rules. GK Tuner implements these rules independently with storage-address regression fixtures; bit-level and overlapping storage remain blocked.

