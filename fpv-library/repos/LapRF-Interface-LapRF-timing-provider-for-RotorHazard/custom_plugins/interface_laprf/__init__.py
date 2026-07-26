''' LapRF Provider '''

import logging
import socket
import time
import gevent
import statistics
import random
import json

from sqlalchemy import Boolean

from . import laprf_protocol as laprf

from eventmanager import Evt
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from BaseHardwareInterface import BaseHardwareInterface, PeakNadirHistory, MarshalType
from Node import Node
from Database import LapSource

logger = logging.getLogger(__name__)

SERIAL_SCHEME = 'serial:'
SOCKET_SCHEME = 'socket://'
CONNECT_TIMEOUT_S = 5
RESPONSE_TIMEOUT_S = 0.5
WRITE_CHILL_TIME_S = 0.01
READ_POLL_RATE = 0.1
MAX_RESPONSE_SAMPLES = 10

def serial_url(port):
    if port.startswith('/'):
        # linux
        return "file:{}".format(port)
    else:
        # windows
        return "serial:{}".format(port)

def socket_url(ip, port):
    return "socket://{}:{}/".format(ip, port)


class SocketStream:
    def __init__(self, socket):
        self.socket = socket

    def write(self, data):
        self.socket.sendall(data)

    def read(self, max_size):
        return self.socket.recv(max_size)

    def close(self):
        self.socket.close()


class LapRFProvider():
    def __init__(self, rhapi):
        self._rhapi = rhapi
        self.startup_device_total = 0
        self.devices = []
        self.interface = None

        # run startup functions
        rhapi.events.on(Evt.STARTUP, self.startup)
        rhapi.events.on(Evt.SHUTDOWN, self.shutdown)
        rhapi.events.on(Evt.RACE_STAGE, self.race_stage)
        rhapi.events.on(Evt.RACE_STOP, self.race_stop)
        rhapi.events.on(Evt.LAPS_CLEAR, self.laps_clear)
        # register UI
        rhapi.config.register_section('LapRF')
        rhapi.ui.register_panel('provider_laprf', 'LapRF General Setup', 'settings')
        rhapi.fields.register_option(
            field=UIField(
                name='device_count',
                label="Device Count",
                field_type=UIFieldType.NUMBER,
                value=1,
                html_attributes={
                    'min': 0
                },
                persistent_section="LapRF",
                persistent_restart=True
            ),
            panel='provider_laprf')
        self.process_config()
        self.init_vars()
        self.init_interface()
        rhapi.interface.add(self.interface)
        if len(self.devices):
            for dev_idx, device in enumerate(self.devices):
                rhapi.fields.register_function_binding(
                    field=UIField(
                        name='address_{}'.format(dev_idx),
                        label="Device {} Address".format(dev_idx + 1),
                        field_type=UIFieldType.TEXT,
                        html_attributes={
                            'min': 0
                        },
                        desc="IP[:port] or USB port"
                    ),
                    getter_fn=self.get_device_address,
                    setter_fn=self.set_device_address,
                    args={
                        'device': dev_idx
                    },
                    panel='provider_laprf')

                rhapi.ui.register_panel(
                    'provider_laprf_detail_{}'.format(dev_idx),
                    'LapRF Device {} ({})'.format(dev_idx + 1, device.name if device.name else 'None'),
                    'settings'
                )
                rhapi.fields.register_function_binding(
                    field=UIField(
                        name='laprf_{}_min_lap_time'.format(dev_idx),
                        label="Minimum Lap Time (ms)",
                        field_type=UIFieldType.NUMBER,
                        html_attributes={
                            'min': 1
                        },
                        desc="1–2Bn (Default: 1500; Recommended: 1)"
                    ),
                    getter_fn=self.get_min_lap,
                    setter_fn=self.set_min_lap,
                    args={
                        'device': dev_idx
                    },
                    panel='provider_laprf_detail_{}'.format(dev_idx))
                for node_idx in range(8):
                    rhapi.fields.register_function_binding(
                        field=UIField(
                            name='laprf_{}_gain_{}'.format(dev_idx, node_idx),
                            label="Gain {}".format(node_idx + 1),
                            field_type=UIFieldType.NUMBER,
                            html_attributes={
                                'min': 0,
                                'max': laprf.MAX_GAIN
                            },
                            desc="0–63 (Typical: 59)"
                        ),
                        getter_fn=self.get_gain,
                        setter_fn=self.set_gain,
                        args={
                            'device': dev_idx,
                            'index': node_idx
                        },
                        panel='provider_laprf_detail_{}'.format(dev_idx))
                    rhapi.fields.register_function_binding(
                        field=UIField(
                            name='laprf_{}_threshold_{}'.format(dev_idx, node_idx),
                            label="Threshold {}".format(node_idx + 1),
                            field_type=UIFieldType.NUMBER,
                            html_attributes={
                                'min': 0,
                                'max': laprf.MAX_THRESHOLD
                            },
                            desc="0–3000 (Typical: 800)"
                        ),
                        getter_fn=self.get_threshold,
                        setter_fn=self.set_threshold,
                        args={
                            'device': dev_idx,
                            'index': node_idx
                        },
                        panel='provider_laprf_detail_{}'.format(dev_idx))
            rhapi.fields.register_function_binding(
                field=UIField(
                    name='laprf_min_lap_time',
                    label="Set All Minimum Lap Times (ms)",
                    field_type=UIFieldType.NUMBER,
                    html_attributes={
                        'min': 1
                    },
                    desc="1–2Bn (Default: 1500; Recommended: 1)"
                ),
                getter_fn=self.get_combined_min_lap,
                setter_fn=self.set_combined_min_lap,
                args=None,
                panel='provider_laprf')
            rhapi.fields.register_function_binding(
                field=UIField(
                    name='laprf_combined_gain',
                    label="Set All Gains",
                    field_type=UIFieldType.NUMBER,
                    html_attributes={
                        'min': 0,
                        'max': laprf.MAX_GAIN
                    },
                    desc="0–63 (Typical: 59)"
                ),
                getter_fn=self.get_combined_gain,
                setter_fn=self.set_combined_gain,
                args=None,
                panel='provider_laprf')
            rhapi.fields.register_function_binding(
                field=UIField(
                    name='laprf_combined_threshold',
                    label="Set All Thresholds",
                    field_type=UIFieldType.NUMBER,
                    html_attributes={
                        'min': 0,
                        'max': laprf.MAX_THRESHOLD
                    },
                    desc="0–3000 (Typical: 800)"
                ),
                getter_fn=self.get_combined_threshold,
                setter_fn=self.set_combined_threshold,
                args=None,
                panel='provider_laprf')
        self._update_status()

    def get_device_address(self, args):
        addrs = self.load_addresses()
        return addrs[args.get('device')]

    def set_device_address(self, value, args):
        any_device_connected = False
        for device in self.devices:
            if device.connected:
                any_device_connected = True
                break

        if any_device_connected:
            self._rhapi.ui.message_notify(f"Stopping LapRF while editing address.")

        self.interface.stop()
        self.init_vars()
        addrs = self.load_addresses()
        addrs[args.get('device')] = value
        stored_val = json.dumps(addrs)
        self._rhapi.config.set('LapRF', 'address', stored_val)
        for dev_idx, device in enumerate(self.devices):
            self._rhapi.ui.register_panel(
                'provider_laprf_detail_{}'.format(dev_idx),
                'LapRF Device {} ({})'.format(dev_idx + 1, addrs[dev_idx] if addrs[dev_idx] else 'None'),
                'settings'
            )
        self._update_status()
        self._rhapi.ui.broadcast_ui('settings')

    def init_vars(self):
        self.gains = [[None] * 8 for _ in range(len(self.devices))]
        self.thresholds = [[None] * 8 for _ in range(len(self.devices))]
        self.min_laps = [None for _ in range(len(self.devices))]

    def init_interface(self):
        logger.info('Initializing LapRF provider')
        self.interface = LapRFInterface(
            devices=self.devices
        )
        self.interface.handle_ping_response = self.handle_ping_response
        self.interface.handle_timeout = self.handle_timeout
        self.interface.init_devices()

    def startup(self, _args):
        self.startup_device_total = len(self.devices)
        logger.debug(f'Number of LapRF devices configured: {self.startup_device_total}')
        self.get_device_config()

        self._rhapi.ui.register_quickbutton(
            panel='provider_laprf',
            name="laprf-btn-connect",
            label="Connect",
            function=self.ui_enable)
        self._rhapi.ui.register_quickbutton(
            panel='provider_laprf',
            name="laprf-btn-disconnect",
            label="Disconnect",
            function=self.ui_disable)
        # self._rhapi.ui.register_quickbutton(
        #    panel='provider_laprf',
        #    name="laprf-btn-ping",
        #    label="Ping",
        #    function=self.ui_ping)
        self._rhapi.ui.register_quickbutton(
            panel='provider_laprf',
            name="laprf-btn-save-all",
            label="Save to Device",
            function=self.ui_save)

    def shutdown(self, _args):
        logger.info('Shutting down LapRF provider')
        self.interface.stop()

    def load_addresses(self):
        count = self._rhapi.config.get('LapRF', 'device_count', as_int=True)
        try:
            addrs = json.loads(self._rhapi.config.get('LapRF', 'address'))
            addrs = addrs[:count]
            while len(addrs) < count:
                addrs.append(None)
            return addrs
        except (TypeError, json.JSONDecodeError) as e:
            return [None] * self._rhapi.config.get('LapRF', 'device_count', as_int=True)

    def process_config(self):
        self.devices = []
        config_addresses = self.load_addresses()
        for addr in config_addresses:
            device_name_str = addr
            addr = self._normalize_addr(addr)
            device = LapRFDevice(addr, device_name_str)
            self.devices.append(device)
            device.sync_callback = self.sync_callback
            device.close_callback = self.close_callback

        if self.interface:
            if len(self.devices) != self.startup_device_total:
                self._rhapi.server.set_restart_required()
            self.interface.devices = self.devices

        return len(self.devices)

    def ui_enable(self, _args):
        if self.process_config():
            if len(self.devices) != self.startup_device_total:
                self._rhapi.ui.message_notify(
                    f"Restart required to use LapRF after changing number of devices. (startup: {self.startup_device_total}; now:{len(self.devices)})")
                self.interface.stop()
            else:
                self.interface.stop()
                self._rhapi.ui.message_notify(f"(Re)starting LapRF...")

                status = self.interface.start()
                if status == True:
                    self._rhapi.ui.message_notify(f"LapRF connected.")
                else:
                    self._rhapi.ui.message_notify(f"Unable to connect to LapRF.")
        self.get_device_config()
        self._update_status()

    def ui_disable(self, _args):
        self._rhapi.ui.message_notify(f"Stopping LapRF.")
        self.interface.stop()
        self.init_vars()

    def ui_ping(self, _args):
        any_device_connected = False
        for device in self.devices:
            if device.connected:
                any_device_connected = True
                break

        if any_device_connected:
            self._rhapi.ui.message_notify(f"Pinging LapRF...")
            ping_cmd = laprf.encode_ping_record(time.monotonic())
            for device in self.devices:
                device.write(ping_cmd)
            self._update_status()
        else:
            self._rhapi.ui.message_notify(f"No connected LapRF devices to ping.")

    def handle_ping_response(self, device, ping_val):
        self._rhapi.ui.message_notify(f"Got Ping from LapRF at {device.name}: {ping_val}")

    def handle_timeout(self, device):
        line1 = self._rhapi.__("Lost connection to LapRF device at {0}").format(device.name)
        line2 = self._rhapi.__('Check network, then reconnect in <a href="/settings">Settings</a>.')
        self._rhapi.ui.message_alert(f"{line1}<br />{line2}")

    def ui_save(self, _args):
        any_device_connected = False
        for device in self.devices:
            if device.connected:
                any_device_connected = True
                break

        if any_device_connected:
            self._rhapi.ui.message_notify(f"Saving settings to LapRF.")
            self.interface.save_all()
        else:
            self._rhapi.ui.message_notify(f"No connected LapRF devices.")

    def _normalize_addr(self, addr):
        if addr and not addr.startswith(SERIAL_SCHEME) and not addr.startswith(SOCKET_SCHEME):
            # addr is not a url
            if addr.startswith('/'):
                # assume serial/file
                addr = serial_url(addr)
            else:
                # assume simple <host>[:<port>]
                host_port = addr.split(':')
                if len(host_port) == 1:
                    host_port = (host_port[0], 5403)
                addr = socket_url(host_port[0], host_port[1])
        return addr

    def get_device_config(self):
        if len(self.interface.devices):
            for dev_idx, device in enumerate(self.interface.devices):
                if device.connected:
                    for idx, node in enumerate(device.nodes):
                        self.gains[dev_idx][idx] = node.gain
                        self.thresholds[dev_idx][idx] = node.threshold
                    self.min_laps[dev_idx] = device.min_lap_time

    def get_combined_gain(self, _args):
        return None

    def get_combined_threshold(self, _args):
        return None

    def get_combined_min_lap(self, _args):
        return None

    def get_gain(self, args):
        return self.gains[args.get('device')][args.get('index')]

    def get_threshold(self, args):
        return self.thresholds[args.get('device')][args.get('index')]

    def get_min_lap(self, args):
        return self.min_laps[args.get('device')]

    def set_combined_gain(self, value, _args):
        self.interface.set_all_gains(int(value))
        for dev_idx, device in enumerate(self.devices):
            for node_idx, _ in enumerate(self.gains[dev_idx]):
                self.gains[dev_idx][node_idx] = int(value)
        self._update_status()

    def set_combined_threshold(self, value, _args):
        self.interface.set_all_thresholds(int(value))
        for dev_idx, device in enumerate(self.devices):
            for node_idx, _ in enumerate(self.thresholds[dev_idx]):
                self.thresholds[dev_idx][node_idx] = int(value)
        self._update_status()

    def set_combined_min_lap(self, value, _args):
        self.interface.set_all_min_lap(int(value))
        for dev_idx, device in enumerate(self.devices):
            self.min_laps[dev_idx] = value
        self._update_status()

    def set_gain(self, value, args):
        if self.devices[args.get('device')].connected:
            self.interface.set_gain(args.get('device'), args.get('index'), int(value))
            self.gains[args.get('device')][args.get('index')] = int(value)
        self._update_status()

    def set_threshold(self, value, args):
        if self.devices[args.get('device')].connected:
            self.interface.set_threshold(args.get('device'), args.get('index'), int(value))
            self.thresholds[args.get('device')][args.get('index')] = int(value)
        self._update_status()

    def set_min_lap(self, value, args):
        if self.devices[args.get('device')].connected:
            self.interface.set_min_lap(args.get('device'), int(value))
            self.min_laps[args.get('device')] = value
        self._update_status()

    def race_stage(self, _args):
        self.interface.set_state(laprf.States.START_RACE)

    def race_stop(self, _args):
        self.interface.set_state(laprf.States.STOP_RACE)

    def laps_clear(self, _args):
        self.interface.set_state(laprf.States.STOP_RACE)

    def sync_callback(self):
        self._update_status()

    def close_callback(self):
        self._update_status()

    def _update_status(self):
        addrs = self.load_addresses()
        if self.interface and len(self.interface.devices):
            for idx, device in enumerate(self.interface.devices):
                md_output = '<p style="text-align:center">'
                if device.connected:
                    if device.sync:
                        md_output += f"Syncronized within {device.sync_ms:.1f}ms\n"
                    else:
                        md_output += f"Synchronizing...\n"
                else:
                    md_output += "Device not connected\n"
                md_output += '</p>'
                self._rhapi.ui.register_markdown('provider_laprf_detail_{}'.format(idx), 'laprf_status', md_output)

        self._rhapi.ui.broadcast_ui('settings', replace_panels=False)


class LapRFNode(Node):
    def __init__(self, device, local_index):
        super().__init__()
        self.local_index = local_index
        self.device = device
        self.is_configured = False
        self.threshold = 0
        self.gain = 0
        self.band_idx = None
        self.channel_idx = None


class LapRFDevice():
    def __init__(self, addr, device_name_str):
        self.name = device_name_str
        self.addr = addr
        self.stream_buffer = bytearray()
        self.io_stream = None
        self.connected = False
        self.sync_ms = None
        self.sync = False
        self.nodes=[]

        self._last_write_timestamp = 0
        self._measuring_response = False
        self._measuring_write_time = False
        self._measuring_read_time = False
        self._measured_write_timestamp = 0
        self._measured_perf_write_timestamp = 0
        self._measured_perf_read_timestamp = 0
        self._time_offset = 0
        self._network_timestamp_samples = []

        for index in range(8):
            node = LapRFNode(self, index)  # New node instance
            node.api_valid_flag = True
            node.node_peak_rssi = 0
            node.node_nadir_rssi = 9999
            node.enter_at_level = 999
            node.exit_at_level = 999
            self.nodes.append(node)

        #self.max_rssi_value = 3500
        #self.voltage = None
        self.min_lap_time = None
        #self.race_start_rtc_time_ms = 0
        #self.race_start_time_request_ts_ms = None

    def connect(self):
        if not self.connected:
            try:
                self.io_stream = self._create_stream()
                self.connected = True
                self.sync = False
                return True
            except Exception:
                logger.warning(f"Unable to connect to LapRF at {self.name}")
                self.io_stream = None
                return False
        return None

    def _create_stream(self):
        if self.addr.startswith(SERIAL_SCHEME):
            port = self.addr[len(SERIAL_SCHEME):]
            io_stream = serial.Serial(port=port, baudrate=115200, timeout=0.25)
        elif self.addr.startswith(SOCKET_SCHEME):
            # strip any trailing /
            end_pos = -1 if self.addr[-1] == '/' else len(self.addr)
            socket_addr = self.addr[len(SOCKET_SCHEME):end_pos]
            host_port = socket_addr.split(':')
            if len(host_port) == 1:
                host_port = (host_port[0], 5403)
            io_stream = SocketStream(socket.create_connection(host_port, timeout=CONNECT_TIMEOUT_S))
        else:
            raise ValueError("Unsupported address: {}".format(self.addr))
        return io_stream

    @property
    def is_configured(self):
        for node in self.nodes:
            if not node.is_configured:
                return False
        return True

    def write(self, data):
        if self.connected:
            chill_remaining_s = self._last_write_timestamp + WRITE_CHILL_TIME_S - time.monotonic()
            if chill_remaining_s > 0:
                gevent.sleep(chill_remaining_s)
            if self._measuring_response:
                self._measured_write_time = time.monotonic()
                self._measured_perf_write_timestamp = time.perf_counter()
            self.io_stream.write(data)
            self._last_write_timestamp = time.monotonic()

    def read(self):
        if self.connected:
            try:
                return self.io_stream.read(512)
            except TimeoutError:
                logger.info(f"LapRF device {self.name} timed out")
                self.close()
                raise

    def close(self):
        if self.connected:
            self.io_stream.close()
            self.io_stream = None
        self.connected = False
        self.close_callback()

    def server_timestamp_from_laprf(self, laprf_raw_timestamp):
        return (laprf_raw_timestamp / 1000000) - self._time_offset

    def request_timestamp(self):
        self._measuring_response = True
        self._measured_perf_write_timestamp = 0
        self.write(laprf.encode_get_rtc_time_record())

    def calc_timestamp_offset(self, laprf_raw_timestamp):
        self._measured_perf_read_timestamp = time.perf_counter()
        if self._measuring_response:
            self._measuring_response = False
            laprf_ts = (laprf_raw_timestamp / 1000000)
            server_delay = self._measured_perf_read_timestamp - self._measured_perf_write_timestamp
            server_oneway = server_delay / 2 if server_delay else 0

            # add sample to sorted store
            offset_sample = {
                'diff': laprf_ts - self._measured_write_time - server_oneway,
                'response': server_delay
            }
            self._network_timestamp_samples.append(offset_sample)
            self._network_timestamp_samples.sort(key=lambda x: x['response'])

            # remove unusable samples
            fastest_sample = self._network_timestamp_samples[0]
            diff_min = fastest_sample['diff'] - fastest_sample['response']
            diff_max = fastest_sample['diff'] + fastest_sample['response']
            self._network_timestamp_samples = [item for item in self._network_timestamp_samples if (
                                               item['diff'] >= diff_min and item['diff'] <= diff_max)]

            # get and store filtered offset
            samples = [item['diff'] for item in self._network_timestamp_samples]
            self._time_offset = statistics.median(samples) if len(samples) else offset_sample['diff']

            self.sync_ms = self._network_timestamp_samples[0]['response'] * 1000

            # continue sampling to improve accuracy
            if (len(self._network_timestamp_samples) < MAX_RESPONSE_SAMPLES and
                    self._network_timestamp_samples[0]['response'] > 0.001):
                logger.debug(f'Synchronizing LapRF... now within {self.sync_ms:.1f}ms ({len(self._network_timestamp_samples)})')
                delay_s = (random.random() * 0.5) + 0.25
                gevent.spawn_later(delay_s, self.request_timestamp)
            else:
                self.sync = True
                self.sync_callback()
                logger.info(f"Synchronized LapRF clock within {self.sync_ms:.1f}ms")

    def sync_callback(self):
        pass

    def close_callback(self):
        pass

class LapRFInterface(BaseHardwareInterface):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update_loop_enabled = False
        self.update_thread = None # Thread for running the main update loop
        self.devices = kwargs['devices']
        self.marshal_type = MarshalType.PASS_PEAK_ONLY
        self.ready_failure_msg = "LapRF device is not connected. Check device, then reconnect in settings."

    @property
    def nodes(self):
        nodes = []
        for device in self.devices:
            for node in device.nodes:
                nodes.append(node)
        return nodes

    @nodes.setter
    def nodes(self, value):
        pass

    @property
    def ready(self):
        for device in self.devices:
            if not device.connected:
                return False
        return True

    #
    # Update Loop
    #

    def init_devices(self):
        for device in self.devices:
            device.connect()
            if device.connected:
                self.configure_device(device)

    def configure_device(self, device):
        try:
            device.write(laprf.encode_get_min_lap_time_record())
            device.write(laprf.encode_get_rf_setup_record())
            self._wait_for_configuration(device, device)
            if not device.is_configured:
                raise Exception(f"LapRF at {device.name} did not respond with RF setup information")
        except:
            pass

    def start(self):
        if self.update_thread is None:
            for device in self.devices:
                device.connect()

            any_device_connected = False
            for device in self.devices:
                if device.connected:
                    any_device_connected = True
                    break

            if any_device_connected:
                self.update_thread = gevent.spawn(self.update_loop)
                for device in self.devices:
                    if device.connected and not device.is_configured:
                        self.configure_device(device)
                    if device.is_configured:
                        device.request_timestamp()
                return True
            return False
        return None

    def stop(self):
        self.log('Stopping LapRF background thread')
        self.update_loop_enabled = False

    def update_loop(self):
        self.log('Starting LapRF background thread')
        self.update_loop_enabled = True
        try:
            while self.update_loop_enabled:
                sleep_interval = READ_POLL_RATE / max(len(self.devices), 1)
                self._update()
                gevent.sleep(sleep_interval)
        except KeyboardInterrupt:
            logger.info("Update thread terminated by keyboard interrupt")
            raise
        self.log('LapRF background thread ended')
        self.update_thread = None
        for device in self.devices:
            device.close()

    def _update(self):
        for device in self.devices:
            try:
                data = device.read()
            except TimeoutError:
                self.handle_timeout(device)
                data = None
            if data:
                end = data.rfind(laprf.EOR)
                if end == -1:
                    device.stream_buffer.extend(data)
                    return
                records = laprf.decode(device.stream_buffer + data[:end + 1])
                device.stream_buffer = bytearray(data[end + 1:])
                for record in records:
                    self._process_message(device, record)

    def _wait_for_configuration(self, configurable_obj, device):
        config_start_ts = time.monotonic()
        while not configurable_obj.is_configured and time.monotonic() < config_start_ts + RESPONSE_TIMEOUT_S:
            if self.update_thread:
                gevent.sleep(RESPONSE_TIMEOUT_S)
            else:
                self._update()
                gevent.sleep(0.01)

    def _process_message(self, device, record: laprf.Event):
        if isinstance(record, laprf.StatusEvent):
            #assert record.battery_voltage is not None
            #device.voltage = millivolts_to_volts(record.battery_voltage)
            rssi_ts = time.monotonic()
            for idx, rssi in enumerate(record.last_rssi):
                if rssi is not None:
                    node = device.nodes[idx]
                    node.current_rssi = rssi
                    node.node_peak_rssi = max(rssi, node.node_peak_rssi)
                    node.node_nadir_rssi = min(rssi, node.node_nadir_rssi)
                    pn_history = PeakNadirHistory(node.index)
                    pn_history.peakRssi = rssi
                    pn_history.peakFirstTime = 0
                    pn_history.peakLastTime = 0
                    self.process_history(node, rssi_ts, pn_history)

        elif isinstance(record, laprf.PassingEvent):
            # logger.debug("LapRF Pass: {}".format(record))
            # assert record.slot_index is not None and record.slot_index > 0
            # assert record.rtc_time is not None
            local_index = record.slot_index - 1
            node = device.nodes[local_index]
            node.pass_peak_rssi = record.peak_height
            node.node_peak_rssi = max(record.peak_height, node.node_peak_rssi)
            if record.peak_height < node.enter_at_level:
                self.pass_record_callback(node, device.server_timestamp_from_laprf(record.rtc_time), LapSource.REALTIME,
                                          peak=record.peak_height, ignore=True)
            else:
                self.pass_record_callback(node, device.server_timestamp_from_laprf(record.rtc_time), LapSource.REALTIME,
                                          peak=record.peak_height, ignore=False)

            # if self.is_racing:
            #     node.pass_history.append(RssiSample(lap_ts_ms + self.race_start_time_ms, pass_peak_rssi))
            # node.pass_count += 1

            # self._notify_pass(node, lap_ts_ms, BaseHardwareInterface.LAP_SOURCE_REALTIME, None)
        elif isinstance(record, laprf.RFSetupEvent):
            # logger.debug("LapRF RFSetup: {}".format(record))
            # assert record.slot_index is not None and record.slot_index > 0
            local_index = record.slot_index - 1
            node = device.nodes[local_index]
            node.band_idx = record.band
            node.channel_idx = record.channel
            old_frequency = node.frequency
            # old_bandChannel = node.bandChannel
            if record.enabled:
                node.frequency = record.frequency
            #     if record.band is not None and record.band >= 1 and record.band <= len(laprf.LIVE_TIME_BANDS) and record.channel is not None and record.channel >= 1 and record.channel <= laprf.MAX_CHANNELS:
            #         node.bandChannel = laprf.LIVE_TIME_BANDS[record.band-1] + str(record.channel)
            #     else:
            #         node.bandChannel = None
            else:
                node.frequency = 0
            #     node.bandChannel = None
            # old_threshold = node.threshold
            # old_gain = node.gain
            node.threshold = record.threshold
            node.gain = record.gain
            node.is_configured = True
            # if node.frequency != old_frequency:
            #     self._notify_frequency_changed(node)
            # if node.bandChannel != old_bandChannel:
            #     self._notify_frequency_changed(node)
            # if node.threshold != old_threshold:
            #     self._notify_threshold_changed(node)
            # if node.gain != old_gain:
            #     self._notify_gain_changed(node)
        elif isinstance(record, laprf.TimeEvent):
            device.calc_timestamp_offset(record.rtc_time)
            # logger.debug("LapRF Time: {}".format(record.rtc_time))
            # assert record.rtc_time is not None
            # if node_manager.race_start_time_request_ts_ms is not None:
            #     server_oneway_ms = round((ms_counter() - node_manager.race_start_time_request_ts_ms)/2)
            #     node_manager.race_start_rtc_time_ms = micros_to_millis(record.rtc_time) - server_oneway_ms
            #     node_manager.race_start_time_request_ts_ms = None
        elif isinstance(record, laprf.SettingsEvent):
            # logger.debug("LapRF Min Lap: {}".format(record.min_lap_time))
            if record.min_lap_time:
                device.min_lap_time = record.min_lap_time
        elif isinstance(record, laprf.PingEvent):
            self.handle_ping_response(device, record.ping)
        else:
            logger.warning("Unsupported record: {}".format(record))

    def handle_ping_response(self, device, ping_val):
        pass

    def handle_timeout(self, device):
        pass

    def set_frequency(self, node_index, frequency, band=0, channel=0):
        node = self.nodes[node_index]
        try:
            band_idx = laprf.FREQUENCY_BANDS.index(band.upper()) + 1 if band else 0
        except ValueError:
            band_idx = 0
        channel_idx = channel if channel else 0

        node.debug_pass_count = 0  # reset debug pass count on frequency change
        self.set_rf_setup(node, frequency, band_idx, channel_idx, node.gain, node.threshold)

    def set_threshold(self, device_idx, node_index, threshold):
        if threshold >= 0 and threshold <= laprf.MAX_THRESHOLD:
            node = self.devices[device_idx].nodes[node_index]
            self.set_rf_setup(node, node.frequency, node.band_idx, node.channel_idx, node.gain, threshold)

    def set_gain(self, device_idx, node_index, gain):
        if gain >= 0 and gain <= laprf.MAX_GAIN:
            node = self.devices[device_idx].nodes[node_index]
            self.set_rf_setup(node, node.frequency, node.band_idx, node.channel_idx, gain, node.threshold)

    def set_min_lap(self, device_idx, min_lap):
        if min_lap >= 0 and min_lap <= laprf.MAX_MIN_LAP:
            self.devices[device_idx].write(laprf.encode_set_min_lap_time_record(min_lap))

    def set_all_thresholds(self, threshold):
        if threshold >= 0 and threshold <= laprf.MAX_THRESHOLD:
            for device in self.devices:
                for node in device.nodes:
                    self.set_rf_setup(node, node.frequency, node.band_idx, node.channel_idx, node.gain, threshold)

    def set_all_gains(self, gain):
        if gain >= 0 and gain <= laprf.MAX_GAIN:
            for device in self.devices:
                for node in device.nodes:
                    self.set_rf_setup(node, node.frequency, node.band_idx, node.channel_idx, gain, node.threshold)

    def set_all_min_lap(self, min_lap):
        if min_lap >= 0 and min_lap <= laprf.MAX_MIN_LAP:
            for device in self.devices:
                device.write(laprf.encode_set_min_lap_time_record(min_lap))

    def save_all(self):
        for device in self.devices:
            device.write(laprf.encode_save_record())

    def set_rf_setup(self, node, frequency, band_idx, channel_idx, gain, threshold):
        device = node.device
        if device.connected:
            local_index = node.local_index + 1 # lapRF is 1-indexed
            enabled = True if frequency else False
            device.write(laprf.encode_set_rf_setup_record(local_index, enabled, band_idx, channel_idx, frequency if frequency else 0, gain, threshold))
            node.is_configured = False
            device.write(laprf.encode_get_rf_setup_record(local_index))
            self._wait_for_configuration(node, device)
            if not node.is_configured:
                logger.error("LapRF did not respond with RF setup information for node {}".format(node))
            if node.frequency != frequency:
                logger.error("LapRF ignored our request to change the frequency of node {} (requested {}, is {})".format(node, frequency, node.frequency))
            if node.threshold != threshold:
                logger.error("LapRF ignored our request to change the threshold of node {} (requested {}, is {})".format(node, threshold, node.threshold))
        else:
            logger.debug(f"LapRF command ignored; device at {device.addr} is not connected")

    def set_state(self, state):
        for device in self.devices:
            device.write(laprf.encode_set_state_record(state))

    def transmit_enter_at_level(self, node, level):
        return level

    def set_enter_at_level(self, node_index, level):
        node = self.nodes[node_index]
        if node.api_valid_flag:
            node.enter_at_level = self.transmit_enter_at_level(node, level)

    def transmit_exit_at_level(self, node, level):
        return level

    def set_exit_at_level(self, node_index, level):
        node = self.nodes[node_index]
        if node.api_valid_flag:
            node.exit_at_level = self.transmit_exit_at_level(node, level)

    def force_end_crossing(self, node_index):
        pass

    def jump_to_bootloader(self):
        self.log("MockInterace - no jump-to-bootloader support")

    def send_status_message(self, msgTypeVal, msgDataVal):
        return False

    def send_shutdown_button_state(self, stateVal):
        return False

    def send_shutdown_started_message(self):
        return False

    def send_server_idle_message(self):
        return False

    def get_fwupd_serial_name(self):
        return None

    def close_fwupd_serial_port(self):
        pass

    def get_info_node_obj(self):
        return self.nodes[0] if self.nodes and len(self.nodes) > 0 else None

    def inc_intf_read_block_count(self):
        pass

    def inc_intf_read_error_count(self):
        pass

    def inc_intf_write_block_count(self):
        pass

    def inc_intf_write_error_count(self):
        pass

    def get_intf_total_error_count(self):
        return 0

    def set_intf_error_report_percent_limit(self, percentVal):
        pass

    def get_intf_error_report_str(self, forceFlag=False):
        return None


def initialize(rhapi):
    # initialize class
    LapRFProvider(rhapi)

