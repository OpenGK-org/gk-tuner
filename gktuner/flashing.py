"""GKFlasher's operations in a native, organized GK Tuner workspace."""
import json
import shutil
import sys
from pathlib import Path
from PyQt5 import QtCore as C, QtWidgets as W
from .flasher_backend import metadata, load_backend, controller_for, BackendJob
from .runtime import backend_setting


# Values name existing GKFlasher GUI handlers, not replacement implementations.
HANDLERS = {
    'Identify ECU': 'display_ecu_identification',
    'Read calibration': 'read_calibration_zone', 'Read program': 'read_program_zone',
    'Read full binary': 'full_read', 'Read DTCs': 'read_dtcs',
    'Flash calibration': 'flash_calibration', 'Flash program': 'flash_program', 'Flash full binary': 'flash_full',
    'Clear adaptive values': 'clear_adaptive_values', 'Correct checksum': 'correct_checksum',
    'BIN to SIE': 'bin_to_sie_conversion', 'SIE to BIN': 'sie_to_bin_conversion',
    'Immobilizer information': 'display_immo_information', 'Reset immobilizer': 'immo_reset',
    'Activate limp-home': 'limp_home', 'Change limp-home password': 'limp_home_teach',
    'Neutralize SMARTRA': 'smartra_neutralize', 'Teach keys': 'teach_keys',
    'Read VIN': 'read_vin', 'Write VIN': 'write_vin', 'VIN to PIN calculator': 'vin_to_pin',
    'RSW - boot software': 'rsw_flash_bsw', 'RSW - application': 'rsw_flash_asw',
    'RSW - calibration': 'rsw_flash_cal', 'RSW - full image': 'rsw_flash_full',
    'RSW - virginize ECU': 'rsw_virginize',
}
OFFLINE = {'Correct checksum', 'BIN to SIE', 'SIE to BIN', 'VIN to PIN calculator'}
BSL = {'BSL - hardware information': '-hwinfo', 'BSL - read internal ROM': '-readint',
       'BSL - read external flash': '-readextflash', 'BSL - write external flash': '-writeextflash'}
LONG_RUNNING = {'KWP logger', 'MTOS'}


class FlashingPanel(W.QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner, self.controller, self.backend = owner, None, None
        self.backend_folder = None
        self.busy, self.job_finished = False, True
        self.job = None
        self.pool = C.QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.actions = {}
        root = W.QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        title = W.QLabel('Flashing & ECU tools')
        title.setObjectName('title')
        root.addWidget(title)
        self.connection = W.QGroupBox('Connection')
        self.connection.setSizePolicy(W.QSizePolicy.Expanding, W.QSizePolicy.Fixed)
        grid = W.QGridLayout(self.connection)
        self.protocol = W.QComboBox()
        self.protocol.addItem('K-Line', 'kline')
        self.protocol.addItem('CAN bus', 'canbus')
        self.interface = W.QComboBox()
        self.interface.setEditable(True)
        self.interface.setMinimumContentsLength(15)
        self.interface.addItem('COM3')
        self.refresh = W.QPushButton('Refresh adapters')
        self.refresh.clicked.connect(self.refresh_interfaces)
        self.ecu = W.QComboBox()
        self.speed = W.QComboBox()
        self.speed.setSizeAdjustPolicy(W.QComboBox.AdjustToContents)
        grid.addWidget(W.QLabel('Protocol'), 0, 0)
        grid.addWidget(self.protocol, 0, 1)
        grid.addWidget(W.QLabel('Adapter interface'), 0, 2)
        grid.addWidget(self.interface, 0, 3)
        grid.addWidget(self.refresh, 0, 4)
        grid.addWidget(W.QLabel('ECU'), 1, 0)
        grid.addWidget(self.ecu, 1, 1)
        grid.addWidget(W.QLabel('Session speed'), 1, 2)
        grid.addWidget(self.speed, 1, 3, 1, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.connection_grid = grid
        self.connection_labels = [grid.itemAtPosition(row, col).widget() for row, col in ((0, 0), (0, 2), (1, 0), (1, 2))]
        self.compact = None
        root.addWidget(self.connection)
        self.tabs = W.QTabWidget()
        self.tabs.setMinimumHeight(240)
        root.addWidget(self.tabs, 3)
        self.input_file = W.QLineEdit()
        self.output_file = W.QLineEdit()
        self.tools_file = W.QLineEdit()
        self.rsw_file = W.QLineEdit()
        self.bsl_file = W.QLineEdit()
        self.mtos_file = W.QLineEdit()

        box = self.tab('Read / Write')
        cards = W.QHBoxLayout()
        self.read_cards = cards
        for title, field, save, names in (
            ('Read ECU', self.output_file, True, ['Read calibration', 'Read program', 'Read full binary']),
            ('Write ECU', self.input_file, False, ['Flash calibration', 'Flash program', 'Flash full binary'])):
            group = W.QGroupBox(title)
            contents = W.QVBoxLayout(group)
            field.setPlaceholderText('Save binary to…' if save else 'Choose saved binary…')
            self.file_row(contents, 'Output' if save else 'Input', field, save)
            for name in names:
                self.buttons(contents, [name])
            cards.addWidget(group, 1)
        box.addLayout(cards)
        self.buttons(box, ['Identify ECU', 'Clear adaptive values'])
        box.addStretch()

        box = self.tab('File tools')
        self.file_row(box, 'Input file', self.tools_file)
        self.tools_output = W.QLineEdit()
        self.file_row(box, 'Save result as', self.tools_output, save=True)
        self.buttons(box, ['Correct checksum', 'BIN to SIE', 'SIE to BIN'])
        note = W.QLabel('Checksum correction runs on the selected output copy. BIN/SIE conversion uses GKFlasher’s original line-swap code.')
        note.setWordWrap(True)
        box.addWidget(note)
        box.addStretch()

        box = self.tab('Diagnostics')
        self.buttons(box, ['Identify ECU', 'Read DTCs', 'Clear adaptive values', 'Read VIN', 'Write VIN'])
        box.addStretch()

        box = self.tab('Immobilizer')
        self.buttons(box, ['Immobilizer information', 'Reset immobilizer', 'Neutralize SMARTRA', 'Teach keys',
                           'Activate limp-home', 'Change limp-home password', 'VIN to PIN calculator'])
        box.addStretch()

        box = self.tab('Recovery')
        rsw = W.QGroupBox('RSW - CAN bootstrap')
        rsw_layout = W.QVBoxLayout(rsw)
        self.file_row(rsw_layout, 'Recovery binary', self.rsw_file)
        self.buttons(rsw_layout, ['RSW - boot software', 'RSW - application', 'RSW - calibration',
                                   'RSW - full image', 'RSW - virginize ECU'])
        note = W.QLabel('Boot software writes Boot1 and Boot2 together. Separate Boot1/Boot2 commands are not implemented by this GKFlasher version.')
        note.setWordWrap(True)
        rsw_layout.addWidget(note)
        box.addWidget(rsw)
        bsl = W.QGroupBox('BSL - bench bootstrap')
        bsl_layout = W.QVBoxLayout(bsl)
        self.file_row(bsl_layout, 'Read output / write input', self.bsl_file)
        options = W.QFormLayout()
        self.bsl_speed = W.QComboBox()
        self.bsl_speed.setEditable(True)
        self.bsl_speed.addItems(['57600', '38400', '19200', '10400'])
        self.bsl_size = W.QLineEdit('0x80000')
        self.bsl_layout = W.QComboBox()
        self.bsl_layout.addItem('Auto-detect flash layout', '')
        self.bsl_layout.addItem('SIMK4x - I4', 'simk4x_i4')
        self.bsl_layout.addItem('SIMK4x - V6', 'simk4x_v6')
        options.addRow('Bootstrap baud rate', self.bsl_speed)
        options.addRow('External read size (hex)', self.bsl_size)
        options.addRow('Write layout', self.bsl_layout)
        bsl_layout.addLayout(options)
        self.buttons(bsl_layout, list(BSL))
        note = W.QLabel('BSL uses GKFlasher’s automatic bench-adapter detection. It does not use the K-Line/CAN interface selector above.')
        note.setWordWrap(True)
        bsl_layout.addWidget(note)
        box.addWidget(bsl)
        box.addStretch()

        box = self.tab('Advanced')
        form = W.QFormLayout()
        self.address_start, self.address_stop = W.QLineEdit(), W.QLineEdit()
        self.address_start.setPlaceholderText('0x80000 or 80000')
        self.address_stop.setPlaceholderText('Exclusive end address')
        form.addRow('Read start (hex)', self.address_start)
        form.addRow('Read stop (hex)', self.address_stop)
        box.addLayout(form)
        self.buttons(box, ['Read address range'])
        self.file_row(box, 'MTOS full binary', self.mtos_file)
        self.mtos_key = W.QLineEdit()
        self.mtos_key.setEchoMode(W.QLineEdit.Password)
        self.mtos_key.setPlaceholderText('Siemens access key (hex)')
        box.addWidget(self.mtos_key)
        self.buttons(box, ['MTOS', 'KWP logger'])
        note = W.QLabel('MTOS is experimental in GKFlasher. The legacy KWP logger uses its built-in CA663056 channels; normal logging is available in Logging.')
        note.setWordWrap(True)
        box.addWidget(note)
        box.addStretch()

        status_row = W.QHBoxLayout()
        self.status = W.QLabel('Ready')
        self.progress = W.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.stop = W.QPushButton('Stop monitor')
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.stop_monitor)
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.progress, 2)
        status_row.addWidget(self.stop)
        root.addLayout(status_row)
        self.console = W.QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(90)
        self.console.setMaximumBlockCount(5000)
        self.console.setPlaceholderText('Operation output')
        root.addWidget(self.console, 2)
        self.build_legacy_prompts(root)

        self.backend_widgets = {'interfacesBox': self.interface, 'ecusBox': self.ecu, 'baudratesBox': self.speed,
                                'readingFileInput': self.output_file, 'flashingFileInput': self.input_file,
                                'checksumFileInput': self.tools_file, 'bslFileInput': self.bsl_file,
                                'rswFileInput': self.rsw_file, 'progressBar': self.progress,
                                'logOutput': self.console, 'bslOutput': self.console}
        self.populate_metadata()
        self.restore_settings()
        self.protocol.currentIndexChanged.connect(self.protocol_changed)
        self.protocol_changed()
        self.interface.currentTextChanged.connect(self.remember_settings)
        self.ecu.currentIndexChanged.connect(self.remember_settings)
        self.speed.currentIndexChanged.connect(self.remember_settings)

    def tab(self, title):
        page = W.QWidget()
        layout = W.QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        scroll = W.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(W.QFrame.NoFrame)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, title)
        return layout

    def layout_for_width(self, width, scale):
        compact = width < round(700 * scale)
        if compact == self.compact:
            return
        self.compact = compact
        grid = self.connection_grid
        while grid.count():
            grid.takeAt(0)
        for col in range(5):
            grid.setColumnStretch(col, 0)
        protocol, adapter, ecu, speed = self.connection_labels
        if compact:
            for row, caption, field in ((0, protocol, self.protocol), (1, adapter, self.interface),
                                        (2, ecu, self.ecu), (3, speed, self.speed)):
                grid.addWidget(caption, row, 0)
                grid.addWidget(field, row, 1)
            grid.addWidget(self.refresh, 1, 2)
            grid.setColumnStretch(1, 1)
        else:
            for row, col, widget in ((0, 0, protocol), (0, 1, self.protocol), (0, 2, adapter),
                                     (0, 3, self.interface), (0, 4, self.refresh), (1, 0, ecu),
                                     (1, 1, self.ecu), (1, 2, speed)):
                grid.addWidget(widget, row, col)
            grid.addWidget(self.speed, 1, 3, 1, 2)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)
        self.read_cards.setDirection(W.QBoxLayout.TopToBottom if compact else W.QBoxLayout.LeftToRight)

    def eventFilter(self, obj, event):
        if event.type() == C.QEvent.Resize:
            self.layout_for_width(obj.width(), getattr(self.owner, 'appearance_scale', 1))
        return False

    def file_row(self, layout, title, field, save=False):
        row = W.QHBoxLayout()
        caption = W.QLabel(title)
        caption.setMinimumWidth(115)
        row.addWidget(caption)
        row.addWidget(field, 1)
        browse = W.QPushButton('Browse…')
        browse.clicked.connect(lambda: self.browse(field, save))
        row.addWidget(browse)
        layout.addLayout(row)

    def buttons(self, layout, names):
        grid = W.QGridLayout()
        for index, name in enumerate(names):
            button = W.QPushButton(name)
            button.clicked.connect(lambda checked=False, name=name: self.run(name))
            grid.addWidget(button, index // 3, index % 3)
            self.actions.setdefault(name, []).append(button)
        layout.addLayout(grid)

    def build_legacy_prompts(self, layout):
        # Keep explicit stdin controls for a GKFlasher CLI operation launched by
        # existing integrations. Normal operations use its native GUI prompts.
        owner = self.owner
        row = W.QHBoxLayout()
        owner.confirm_yes = W.QPushButton('Confirm prompt')
        owner.confirm_no = W.QPushButton('Decline')
        owner.flash_response = W.QLineEdit()
        owner.flash_response.setPlaceholderText('GKFlasher response')
        owner.send_response = W.QPushButton('Send')
        for widget in (owner.confirm_yes, owner.confirm_no, owner.flash_response, owner.send_response):
            widget.setEnabled(False)
            row.addWidget(widget)
        owner.confirm_yes.clicked.connect(lambda: owner.respond_flash_prompt('y'))
        owner.confirm_no.clicked.connect(lambda: owner.respond_flash_prompt('n'))
        owner.send_response.clicked.connect(lambda: owner.respond_flash_prompt(owner.flash_response.text()))
        self.prompt_widget = W.QWidget()
        self.prompt_widget.setLayout(row)
        self.prompt_widget.hide()
        layout.addWidget(self.prompt_widget)
        owner.flash_protocol, owner.flash_interface = self.protocol, self.interface.lineEdit()
        owner.flash_binary, owner.console = self.input_file, self.console
        owner.flash_run = self.actions['Identify ECU'][0]
        owner.flash_operation = W.QComboBox(self)
        owner.flash_operation.addItems(['Identify ECU', 'Read full binary', 'Read calibration', 'Flash calibration', 'Flash program', 'Flash full binary'])
        owner.flash_operation.hide()

    def populate_metadata(self):
        self.ecu.clear()
        self.speed.clear()
        self.ecu.addItem('Auto-detect ECU', -1)
        self.speed.addItem('Default - 10,400 baud', -1)
        folder = backend_setting(self.owner.settings, 'GKFlasher')
        try:
            ecus, rates = metadata(folder)
            for index, entry in enumerate(ecus):
                self.ecu.addItem(entry['ecu']['name'], index)
            for index, speed in rates.items():
                self.speed.addItem(f'{speed:,} baud', index)
        except Exception as exc:
            self.append_log(f'GKFlasher catalog could not load: {exc}')

    def restore_settings(self):
        try:
            state = json.loads(self.owner.settings.value('flasher_ui', '{}'))
            self.protocol.setCurrentIndex(max(0, self.protocol.findData(state.get('protocol', 'kline'))))
            self.interface.setCurrentText(state.get('interface', 'COM3'))
            self.ecu.setCurrentIndex(max(0, self.ecu.findData(state.get('ecu', -1))))
            self.speed.setCurrentIndex(max(0, self.speed.findData(state.get('speed', -1))))
        except (ValueError, TypeError):
            pass

    def remember_settings(self, *args):
        self.owner.settings.setValue('flasher_ui', json.dumps({'protocol': self.protocol.currentData(),
                                    'interface': self.interface.currentText(), 'ecu': self.ecu.currentData(),
                                    'speed': self.speed.currentData()}))

    def protocol_changed(self):
        can = self.protocol.currentData() == 'canbus'
        text = self.interface.currentText()
        if can and text.upper().startswith('COM'):
            self.interface.setCurrentText('PCAN_USBBUS1')
        elif not can and text.upper().startswith('PCAN'):
            self.interface.setCurrentText('COM3')
        self.speed.setEnabled(not can and not self.busy)
        if can:
            self.speed.setCurrentIndex(0)
        for name, buttons in self.actions.items():
            if name.startswith('RSW'):
                for button in buttons:
                    button.setEnabled(can and not self.busy)
                    button.setToolTip('RSW requires CAN bus' if not can else '')
        self.remember_settings()

    def append_log(self, text):
        self.console.appendPlainText(str(text))

    def browse(self, field, save=False):
        callback = W.QFileDialog.getSaveFileName if save else W.QFileDialog.getOpenFileName
        path, _ = callback(self, 'Choose file', field.text(), 'Binary / SIE (*.bin *.sie);;All files (*)')
        if path:
            field.setText(path)

    def ensure_backend(self):
        folder = Path(self.owner.flasher_path.text()).resolve()
        if self.backend_folder != folder:
            self.backend = load_backend(folder)
            displayed = [self.ecu.itemText(index) for index in range(1, self.ecu.count())]
            actual = [entry['ecu']['name'] for entry in self.backend.ECU_IDENTIFICATION_TABLE]
            if displayed != actual:
                raise ValueError('Restart GK Tuner after changing GKFlasher folders so the ECU selector matches its backend.')
            self.controller = controller_for(self, self.backend)
            self.backend_folder = folder
        return self.controller

    def refresh_interfaces(self):
        try:
            self.ensure_backend()
            hardware = self.backend.KLineHardware if self.protocol.currentData() == 'kline' else self.backend.CanHardware
            current = self.interface.currentText()
            ports = list(hardware.available_ports())
            self.interface.clear()
            for port in ports:
                self.interface.addItem(str(port.port))
                self.interface.setItemData(self.interface.count() - 1, port.description(), C.Qt.ToolTipRole)
            self.interface.setCurrentText(current)
            self.status.setText(f'{len(ports)} adapters found')
        except Exception as exc:
            self.owner.error(str(exc))

    def validate(self, name):
        if self.busy or self.owner.process.state() != C.QProcess.NotRunning:
            raise ValueError('Wait for the current GKFlasher operation to finish.')
        if name not in OFFLINE and self.owner.session and self.owner.session.snapshot()['state'] in ('connecting', 'recording', 'stopping'):
            raise ValueError('Stop logging and wait for the adapter to release before using GKFlasher.')
        if name.startswith('RSW') and self.protocol.currentData() != 'canbus':
            raise ValueError('RSW requires a CAN bus interface.')
        writes = name.startswith(('Flash ', 'RSW -', 'BSL - write')) or name in ('MTOS', 'Reset immobilizer', 'Neutralize SMARTRA', 'Teach keys', 'Write VIN', 'Activate limp-home', 'Change limp-home password', 'Clear adaptive values')
        if name.startswith('Flash ') and (self.owner.document and self.owner.document.dirty or any(getattr(e, 'pending', False) for e in self.owner.open_editors.values())):
            raise ValueError('Save or discard pending map changes before flashing a saved binary.')
        file = None
        if name.startswith('Flash '): file = self.input_file
        elif name in ('Correct checksum', 'BIN to SIE', 'SIE to BIN'): file = self.tools_file
        elif name.startswith('RSW') and name != 'RSW - virginize ECU': file = self.rsw_file
        elif name == 'BSL - write external flash': file = self.bsl_file
        elif name == 'MTOS': file = self.mtos_file
        if file is not None and not Path(file.text()).is_file():
            raise ValueError('Choose an existing input file.')
        if name in ('Read calibration', 'Read program', 'Read full binary', 'Read address range'):
            self.require_output(self.output_file)
        elif name in ('BSL - read internal ROM', 'BSL - read external flash'):
            self.require_output(self.bsl_file)
        if name == 'Read address range':
            start, stop = int(self.address_start.text(), 16), int(self.address_stop.text(), 16)
            if not 0 <= start < stop:
                raise ValueError('Read stop must be greater than read start.')
        if name == 'MTOS':
            key = int(self.mtos_key.text(), 16)
            if not 0 <= key <= 0xffffffff:
                raise ValueError('MTOS key must fit in 32 bits.')
        if name == 'KWP logger' and Path('log.csv').exists():
            raise ValueError('GKFlasher’s legacy logger writes log.csv. Rename the existing log.csv capture before starting another.')
        if name in BSL:
            if not 1 <= int(self.bsl_speed.currentText()) <= 1000000:
                raise ValueError('Choose a valid BSL baud rate.')
            if name == 'BSL - read external flash' and int(self.bsl_size.text(), 16) <= 0:
                raise ValueError('Choose a positive external flash read size.')
        if writes:
            text = f'{name}\nECU: {self.ecu.currentText()}\nProtocol: {self.protocol.currentText()}\nInterface: {self.interface.currentText()}'
            if file is not None:
                text += f'\nFile: {Path(file.text()).resolve()}'
            if W.QMessageBox.question(self, 'Review operation', text + '\n\nContinue?', W.QMessageBox.Yes | W.QMessageBox.Cancel, W.QMessageBox.Cancel) != W.QMessageBox.Yes:
                return False
        return True

    def require_output(self, field):
        if not field.text().strip():
            self.browse(field, save=True)
        if not field.text().strip():
            raise ValueError('Choose an output filename.')
        if Path(field.text()).exists():
            raise ValueError('Choose a new output filename to preserve existing files.')

    def set_busy(self, busy, name=''):
        self.busy = busy
        self.connection.setEnabled(not busy)
        self.tabs.setEnabled(not busy)
        self.stop.setEnabled(busy and name in LONG_RUNNING)
        self.status.setText(name if busy else 'Ready')
        if not busy:
            self.protocol_changed()

    def run(self, name):
        if self.busy or self.owner.process.state() != C.QProcess.NotRunning:
            return self.owner.error('Wait for the current GKFlasher operation to finish.')
        try:
            if not self.validate(name):
                return
            controller = self.ensure_backend()
            self.set_busy(True, name)
            self.job_finished = False
            self.progress.setValue(0)
            self.append_log(f'\n{name}')
            if name in ('Correct checksum', 'BIN to SIE', 'SIE to BIN'):
                self.file_tool(name)
                self.job_finished = True
                self.finish_if_idle()
                return
            callback = self.callback_for(name)
            def cleanup(signals):
                if not controller.promptPending:
                    controller._close_bus(signals.log)
            self.job = BackendJob(callback, cleanup, name in LONG_RUNNING)
            self.job.signals.log.connect(self.append_log)
            self.job.signals.error.connect(self.job_error)
            self.job.signals.progress.connect(self.progress_update)
            self.job.signals.finished.connect(self.worker_finished)
            self.pool.start(self.job)
        except Exception as exc:
            self.job_finished = True
            self.set_busy(False)
            self.owner.error(str(exc))

    def file_tool(self, name):
        source = Path(self.tools_file.text()).resolve()
        target_text = self.tools_output.text().strip()
        if not target_text:
            suffix = '.sie' if name == 'BIN to SIE' else '.bin'
            default = str(source.with_name(source.stem + ('-checksum' if name == 'Correct checksum' else '-converted') + suffix))
            target_text = W.QFileDialog.getSaveFileName(self, 'Save result as', default, 'Binary / SIE (*.bin *.sie)')[0]
            if not target_text:
                return
            self.tools_output.setText(target_text)
        target = Path(target_text).resolve()
        if target == source or target.exists():
            raise ValueError('Choose a new output file to preserve the input and existing files.')
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == 'Correct checksum':
            if self.backend.detect_offsets(source.read_bytes()) is None:
                raise ValueError('GKFlasher could not identify a supported checksum layout in this file.')
            shutil.copyfile(source, target)
            self.controller.checksumFileInput = W.QLineEdit(str(target), self.controller)
            try:
                self.controller.correct_checksum()
            finally:
                self.controller.checksumFileInput.deleteLater()
                self.controller.checksumFileInput = self.tools_file
        else:
            # GKFlasher's conversion generates a sibling with a fixed extension.
            # Stage only a copy and move its result to the user's chosen name.
            import tempfile
            with tempfile.TemporaryDirectory(dir=target.parent) as folder:
                staged = Path(folder) / ('input.bin' if name == 'BIN to SIE' else 'input.sie')
                shutil.copyfile(source, staged)
                function = self.backend.generate_sie if name == 'BIN to SIE' else self.backend.generate_bin
                function(str(staged))
                converted = staged.with_suffix('.sie' if name == 'BIN to SIE' else '.bin')
                if not converted.is_file():
                    raise ValueError('GKFlasher did not generate a converted file. See operation output.')
                shutil.move(str(converted), target)
        self.append_log(f'Result: {target}')

    def callback_for(self, name):
        controller, backend = self.controller, self.backend
        if name in HANDLERS:
            function = getattr(controller, HANDLERS[name])
            return lambda signals: function(progress_callback=signals.progress, log_callback=signals.log)
        if name in BSL:
            args = [self.bsl_speed.currentText(), BSL[name]]
            if name.startswith('BSL - read'):
                args += ['0x8000' if name == 'BSL - read internal ROM' else hex(int(self.bsl_size.text(), 16)), str(Path(self.bsl_file.text()).resolve())]
            elif name == 'BSL - write external flash':
                args += [str(Path(self.bsl_file.text()).resolve())]
                if self.bsl_layout.currentData(): args.append(self.bsl_layout.currentData())
            return lambda signals: backend.bsl.execute_bsl(args, progress_callback=backend.Progress(signals.progress, 100), log_callback2=signals.log)
        start_stop = (int(self.address_start.text(), 16), int(self.address_stop.text(), 16)) if name == 'Read address range' else None
        mtos_key = int(self.mtos_key.text(), 16) if name == 'MTOS' else None
        mtos_path = self.mtos_file.text()
        def connected(signals):
            ecu = controller.initialize_ecu(signals.log)
            if not ecu:
                return
            try:
                if name == 'Read address range':
                    controller.gui_read_eeprom(ecu, address_start=start_stop[0], address_stop=start_stop[1], output_filename=self.output_file.text(), log_callback=signals.log, progress_callback=signals.progress)
                elif name == 'MTOS':
                    from flasher.mtos import mtos_handler
                    mtos_handler(ecu, mtos_path, mtos_key)
                elif name == 'KWP logger':
                    from flasher.logging import logger
                    signals.log.emit('GKFlasher writes the legacy capture to log.csv in the application working folder.')
                    logger(ecu)
                else:
                    raise ValueError('Unknown GKFlasher operation.')
            finally:
                controller.disconnect_ecu(ecu)
        return connected

    def stop_monitor(self):
        if self.job and self.job.interruptible:
            self.stop.setEnabled(False)
            self.status.setText('Stopping and releasing adapter…')
            self.job.stop_event.set()

    def progress_update(self, value):
        if len(value) > 1:
            self.progress.setMaximum(value[0])
            self.progress.setValue(0)
        else:
            self.progress.setValue(value[0])

    def job_error(self, message):
        self.append_log(f'Error: {message}')

    def worker_finished(self):
        self.job_finished = True
        self.finish_if_idle()

    def finish_if_idle(self):
        if self.job_finished and (self.controller is None or not self.controller.promptPending):
            if self.controller is not None:
                try:
                    self.controller._close_bus(self.controller.log_signal)
                except Exception as exc:
                    self.append_log(f'Adapter release failed: {exc}')
            self.set_busy(False)
