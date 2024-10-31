import logging
import ssl
import warnings
import threading
import time
import os
from prometheus_client import start_http_server, Gauge
import xml.etree.ElementTree as ET
import re

# Отключаем предупреждения о депрекации
warnings.filterwarnings(action='ignore', module='.*paramiko.*')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Метрики для экспорта в Prometheus
METRICS = {
    'volumes': {
        'capacity': Gauge('ibm_volume_capacity', 'Total capacity of volume', labelnames=['device_name', 'volume_id']),
        'used_capacity': Gauge('ibm_volume_used_capacity', 'Used capacity of volume', labelnames=['device_name', 'volume_id']),
        'free_capacity': Gauge('ibm_volume_free_capacity', 'Free capacity of volume', labelnames=['device_name', 'volume_id']),
        'iops': Gauge('ibm_volume_iops', 'IOPS of volume', labelnames=['device_name', 'volume_id']),
        'latency': Gauge('ibm_volume_latency', 'Latency of volume', labelnames=['device_name', 'volume_id']),
    },
    'pools': {
        'capacity': Gauge('ibm_pool_capacity', 'Total capacity of pool', labelnames=['device_name', 'pool_id']),
        'used_capacity': Gauge('ibm_pool_used_capacity', 'Used capacity of pool', labelnames=['device_name', 'pool_id']),
        'free_capacity': Gauge('ibm_pool_free_capacity', 'Free capacity of pool', labelnames=['device_name', 'pool_id']),
    },
    'disks': {
        'capacity': Gauge('ibm_disk_capacity', 'Total capacity of disk', labelnames=['device_name', 'disk_idx']),
        'used_capacity': Gauge('ibm_disk_used_capacity', 'Used capacity of disk', labelnames=['device_name', 'disk_idx']),
        'free_capacity': Gauge('ibm_disk_free_capacity', 'Free capacity of disk', labelnames=['device_name', 'disk_idx']),
        'read_ops': Gauge('ibm_disk_read_ops', 'Read operations of disk', labelnames=['device_name', 'disk_idx']),
        'write_ops': Gauge('ibm_disk_write_ops', 'Write operations of disk', labelnames=['device_name', 'disk_idx']),
        'read_bytes': Gauge('ibm_disk_read_bytes', 'Read bytes of disk', labelnames=['device_name', 'disk_idx']),
        'write_bytes': Gauge('ibm_disk_write_bytes', 'Write bytes of disk', labelnames=['device_name', 'disk_idx']),
        'read_errors': Gauge('ibm_disk_read_errors', 'Read errors of disk', labelnames=['device_name', 'disk_idx']),
        'write_errors': Gauge('ibm_disk_write_errors', 'Write errors of disk', labelnames=['device_name', 'disk_idx']),
    },
    'managed_disks': {
        'capacity': Gauge('ibm_managed_disk_capacity', 'Capacity of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'used_capacity': Gauge('ibm_managed_disk_used_capacity', 'Used capacity of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'free_capacity': Gauge('ibm_managed_disk_free_capacity', 'Free capacity of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'read_ops': Gauge('ibm_managed_disk_read_ops', 'Read operations of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'write_ops': Gauge('ibm_managed_disk_write_ops', 'Write operations of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'read_bytes': Gauge('ibm_managed_disk_read_bytes', 'Read bytes of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'write_bytes': Gauge('ibm_managed_disk_write_bytes', 'Write bytes of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'read_errors': Gauge('ibm_managed_disk_read_errors', 'Read errors of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'write_errors': Gauge('ibm_managed_disk_write_errors', 'Write errors of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'ca_dav': Gauge('ibm_managed_disk_ca_dav', 'CA DAV of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'ca_dtav': Gauge('ibm_managed_disk_ca_dtav', 'CA DTAV of managed disk', labelnames=['device_name', 'managed_disk_id']),
        'ca_dfav': Gauge('ibm_managed_disk_ca_dfav', 'CA DFAV of managed disk', labelnames=['device_name', 'managed_disk_id']),
    },
    'virtual_disks': {
        'capacity': Gauge('ibm_virtual_disk_capacity', 'Capacity of virtual disk', labelnames=['device_name', 'virtual_disk_id']),
        'used_capacity': Gauge('ibm_virtual_disk_used_capacity', 'Used capacity of virtual disk', labelnames=['device_name', 'virtual_disk_id']),
        'free_capacity': Gauge('ibm_virtual_disk_free_capacity', 'Free capacity of virtual disk', labelnames=['device_name', 'virtual_disk_id']),
        'iops': Gauge('ibm_virtual_disk_iops', 'IOPS of virtual disk', labelnames=['device_name', 'virtual_disk_id']),
        'latency': Gauge('ibm_virtual_disk_latency', 'Latency of virtual disk', labelnames=['device_name', 'virtual_disk_id']),
    },
    'ports': {
        'heartbeat_total': Gauge('ibm_port_heartbeat_total', 'Total heartbeats of port', labelnames=['device_name', 'port_id']),
        'heartbeat_received': Gauge('ibm_port_heartbeat_received', 'Heartbeat received of port', labelnames=['device_name', 'port_id']),
        'temperature': Gauge('ibm_port_temperature', 'Temperature of port', labelnames=['device_name', 'port_id']),
        'tx_power': Gauge('ibm_port_tx_power', 'TX Power of port', labelnames=['device_name', 'port_id']),
        'rx_power': Gauge('ibm_port_rx_power', 'RX Power of port', labelnames=['device_name', 'port_id']),
        'hsw': Gauge('ibm_port_hsw', 'HSW metric of port', labelnames=['device_name', 'port_id']),
    },
    'nodes': {
        'cpu_busy': Gauge('ibm_node_cpu_busy', 'CPU busy time', labelnames=['device_name', 'node_id']),
        'cpu_system': Gauge('ibm_node_cpu_system', 'CPU system time', labelnames=['device_name', 'node_id']),
        'cpu_completions': Gauge('ibm_node_cpu_completions', 'CPU completions', labelnames=['device_name', 'node_id']),
    },
    'cpu_cores': {
        'system_time': Gauge('ibm_cpu_core_system_time', 'System time per CPU core', labelnames=['device_name', 'node_id', 'core_id']),
        'completions': Gauge('ibm_cpu_core_completions', 'Completions per CPU core', labelnames=['device_name', 'node_id', 'core_id']),
    },
    'dimm': {
        # Удаляем строковые метрики и используем их как метки для корректированных ошибок
        'corrected_errors': Gauge('ibm_node_dimm_corrected_errors', 'DIMM corrected errors', labelnames=['device_name', 'node_id', 'dimm_id', 'manufacture', 'serial_number']),
    },
}

def convert_size(size_str):
    """Конвертирует строку размера, содержащую единицы измерения, в число."""
    size_str = size_str.upper().strip()
    try:
        if size_str.endswith('TB'):
            return float(size_str.replace('TB', '').strip()) * 1_000_000_000_000
        elif size_str.endswith('GB'):
            return float(size_str.replace('GB', '').strip()) * 1_000_000_000
        elif size_str.endswith('MB'):
            return float(size_str.replace('MB', '').strip()) * 1_000_000
        elif size_str.endswith('KB'):
            return float(size_str.replace('KB', '').strip()) * 1_000
        elif size_str.endswith('B'):
            return float(size_str.replace('B', '').strip())
        elif size_str.endswith('G'):
            return float(size_str.replace('G', '').strip()) * 1_000_000_000
        elif size_str.endswith('M'):
            return float(size_str.replace('M', '').strip()) * 1_000_000
        elif size_str.endswith('K'):
            return float(size_str.replace('K', '').strip()) * 1_000
        else:
            return float(size_str)
    except ValueError as e:
        logging.error(f"Error converting size: {e}")
        return 0

def collect_metrics_from_file(file_path):
    logging.info(f"Сбор метрик из файла {file_path}.")
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Extract namespace
        namespace = re.match(r'\{.*\}', root.tag).group(0) if re.match(r'\{.*\}', root.tag) else ''
        ns = {
            'nodeStats': 'http://ibm.com/storage/management/performance/api/2006/01/nodeStats',
            'driveStats': 'http://ibm.com/storage/management/performance/api/2010/03/driveStats',
            'managedDiskStats': 'http://ibm.com/storage/management/performance/api/2003/04/diskStats',
            'vDiskStats': 'http://ibm.com/storage/management/performance/api/2005/08/vDiskStats'
        }

        contains = root.attrib.get('contains', '')
        device_name = root.attrib.get('cluster', 'unknown')

        if 'nodeStats' in contains:
            collect_node_metrics(root, ns['nodeStats'], device_name)
        if 'driveStats' in contains:
            collect_drive_metrics(root, ns['driveStats'], device_name)
        if 'managedDiskStats' in contains:
            collect_managed_disk_metrics(root, ns['managedDiskStats'], device_name)
        if 'virtualDiskStats' in contains:
            collect_virtual_disk_metrics(root, ns['vDiskStats'], device_name)
        if 'nodeStats' in contains or 'driveStats' in contains or 'managedDiskStats' in contains or 'virtualDiskStats' in contains:
            collect_port_metrics(root, device_name)
    except ET.ParseError as e:
        logging.error(f"Ошибка парсинга XML файла {file_path}: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при обработке файла {file_path}: {e}")

def collect_node_metrics(root, namespace, device_name):
    try:
        logging.info("Сбор метрик узла.")
        cpu_element = root.find('.//nodeStats:cpu', {'nodeStats': namespace})
        if cpu_element is not None:
            cpu_busy = int(cpu_element.attrib.get('busy', 0))
            cpu_system = int(cpu_element.attrib.get('system', 0))
            cpu_completions = int(cpu_element.attrib.get('comp', 0))
            node_id = root.attrib.get('id', 'unknown')

            METRICS['nodes']['cpu_busy'].labels(device_name, node_id).set(cpu_busy)
            METRICS['nodes']['cpu_system'].labels(device_name, node_id).set(cpu_system)
            METRICS['nodes']['cpu_completions'].labels(device_name, node_id).set(cpu_completions)

        for cpu_core in root.findall('.//nodeStats:cpu_core', {'nodeStats': namespace}):
            core_id = cpu_core.attrib.get('id', 'unknown')
            system_time = int(cpu_core.attrib.get('system', 0))
            completions = int(cpu_core.attrib.get('comp', 0))

            METRICS['cpu_cores']['system_time'].labels(device_name, node_id, core_id).set(system_time)
            METRICS['cpu_cores']['completions'].labels(device_name, node_id, core_id).set(completions)

        for dimm in root.findall('.//nodeStats:dimm', {'nodeStats': namespace}):
            dimm_id = dimm.attrib.get('id', 'unknown')
            manufacture = dimm.attrib.get('manu', 'unknown')
            serial_number = dimm.attrib.get('sn', 'unknown')
            corrected_errors = int(dimm.attrib.get('ce', 0))

            # Используем corrected_errors с метками manufacture и serial_number
            METRICS['dimm']['corrected_errors'].labels(device_name, node_id, dimm_id, manufacture, serial_number).set(corrected_errors)
    except Exception as e:
        logging.error(f"Ошибка при сборе метрик узла: {e}")

def collect_drive_metrics(root, namespace, device_name):
    try:
        logging.info("Сбор метрик дисков.")
        for mdsk in root.findall('.//driveStats:mdsk', {'driveStats': namespace}):
            disk_idx = mdsk.attrib.get('idx', 'unknown')
            ro = int(mdsk.attrib.get('ro', 0))
            wo = int(mdsk.attrib.get('wo', 0))
            rb = int(mdsk.attrib.get('rb', 0))
            wb = int(mdsk.attrib.get('wb', 0))
            re = int(mdsk.attrib.get('re', 0))
            we = int(mdsk.attrib.get('we', 0))
            rq = int(mdsk.attrib.get('rq', 0))
            wq = int(mdsk.attrib.get('wq', 0))
            # Additional metrics as needed

            capacity = ro + wo
            used_capacity = rb
            free_capacity = wb
            read_ops = re
            write_ops = we
            read_bytes = rq
            write_bytes = wq

            METRICS['disks']['capacity'].labels(device_name, disk_idx).set(capacity)
            METRICS['disks']['used_capacity'].labels(device_name, disk_idx).set(used_capacity)
            METRICS['disks']['free_capacity'].labels(device_name, disk_idx).set(free_capacity)
            METRICS['disks']['read_ops'].labels(device_name, disk_idx).set(read_ops)
            METRICS['disks']['write_ops'].labels(device_name, disk_idx).set(write_ops)
            METRICS['disks']['read_bytes'].labels(device_name, disk_idx).set(read_bytes)
            METRICS['disks']['write_bytes'].labels(device_name, disk_idx).set(write_bytes)
            # Add more metrics if needed
    except Exception as e:
        logging.error(f"Ошибка при сборе метрик дисков: {e}")

def collect_managed_disk_metrics(root, namespace, device_name):
    try:
        logging.info("Сбор метрик управляемых дисков.")
        for mdsk in root.findall('.//managedDiskStats:mdsk', {'managedDiskStats': namespace}):
            managed_disk_id = mdsk.attrib.get('id', 'unknown')
            ro = int(mdsk.attrib.get('ro', 0))
            wo = int(mdsk.attrib.get('wo', 0))
            rb = int(mdsk.attrib.get('rb', 0))
            wb = int(mdsk.attrib.get('wb', 0))
            re = int(mdsk.attrib.get('re', 0))
            we = int(mdsk.attrib.get('we', 0))
            rq = int(mdsk.attrib.get('rq', 0))
            wq = int(mdsk.attrib.get('wq', 0))

            capacity = ro + wo
            used_capacity = rb
            free_capacity = wb
            read_ops = re
            write_ops = we
            read_bytes = rq
            write_bytes = wq

            METRICS['managed_disks']['capacity'].labels(device_name, managed_disk_id).set(capacity)
            METRICS['managed_disks']['used_capacity'].labels(device_name, managed_disk_id).set(used_capacity)
            METRICS['managed_disks']['free_capacity'].labels(device_name, managed_disk_id).set(free_capacity)
            METRICS['managed_disks']['read_ops'].labels(device_name, managed_disk_id).set(read_ops)
            METRICS['managed_disks']['write_ops'].labels(device_name, managed_disk_id).set(write_ops)
            METRICS['managed_disks']['read_bytes'].labels(device_name, managed_disk_id).set(read_bytes)
            METRICS['managed_disks']['write_bytes'].labels(device_name, managed_disk_id).set(write_bytes)
            # Parse <ca> child element if needed
            ca = mdsk.find('.//managedDiskStats:ca', {'managedDiskStats': namespace})
            if ca is not None:
                dav = float(ca.attrib.get('dav', 0))
                dtav = float(ca.attrib.get('dtav', 0))
                dfav = float(ca.attrib.get('dfav', 0))

                METRICS['managed_disks']['ca_dav'].labels(device_name, managed_disk_id).set(dav)
                METRICS['managed_disks']['ca_dtav'].labels(device_name, managed_disk_id).set(dtav)
                METRICS['managed_disks']['ca_dfav'].labels(device_name, managed_disk_id).set(dfav)
    except Exception as e:
        logging.error(f"Ошибка при сборе метрик управляемых дисков: {e}")

def collect_virtual_disk_metrics(root, namespace, device_name):
    try:
        logging.info("Сбор метрик виртуальных дисков.")
        for vdsk in root.findall('.//vDiskStats:vdsk', {'vDiskStats': namespace}):
            virtual_disk_id = vdsk.attrib.get('id', 'unknown')
            ro = int(vdsk.attrib.get('ro', 0))
            wo = int(vdsk.attrib.get('wo', 0))
            rb = int(vdsk.attrib.get('rb', 0))
            wb = int(vdsk.attrib.get('wb', 0))
            ctr = int(vdsk.attrib.get('ctr', 0))
            ctw = int(vdsk.attrib.get('ctw', 0))
            ctrh = float(vdsk.attrib.get('ctrh', 0))

            capacity = ro + wo
            used_capacity = rb
            free_capacity = wb
            iops = ctr + ctw
            latency = ctrh

            METRICS['virtual_disks']['capacity'].labels(device_name, virtual_disk_id).set(capacity)
            METRICS['virtual_disks']['used_capacity'].labels(device_name, virtual_disk_id).set(used_capacity)
            METRICS['virtual_disks']['free_capacity'].labels(device_name, virtual_disk_id).set(free_capacity)
            METRICS['virtual_disks']['iops'].labels(device_name, virtual_disk_id).set(iops)
            METRICS['virtual_disks']['latency'].labels(device_name, virtual_disk_id).set(latency)
    except Exception as e:
        logging.error(f"Ошибка при сборе метрик виртуальных дисков: {e}")

def collect_port_metrics(root, device_name):
    try:
        logging.info("Сбор метрик портов.")
        for port in root.findall('.//port'):
            port_id = port.attrib.get('id', 'unknown')
            hbt = int(port.attrib.get('hbt', 0))
            hbr = int(port.attrib.get('hbr', 0))
            temperature = int(port.attrib.get('tmp', 0))
            tx_power = int(port.attrib.get('txpwr', 0))
            rx_power = int(port.attrib.get('rxpwr', 0))
            hsw = int(port.attrib.get('hsw', 0))

            METRICS['ports']['heartbeat_total'].labels(device_name, port_id).set(hbt)
            METRICS['ports']['heartbeat_received'].labels(device_name, port_id).set(hbr)
            METRICS['ports']['temperature'].labels(device_name, port_id).set(temperature)
            METRICS['ports']['tx_power'].labels(device_name, port_id).set(tx_power)
            METRICS['ports']['rx_power'].labels(device_name, port_id).set(rx_power)
            METRICS['ports']['hsw'].labels(device_name, port_id).set(hsw)
    except Exception as e:
        logging.error(f"Ошибка при сборе метрик портов: {e}")


def get_latest_files(local_directory):
    latest_files = {}
    pattern = re.compile(r'^(Nd|Nm|Nn|Nv)_stats_78E374R-([12])_([0-9]{6})_([0-9]{6})$')

    for file in os.listdir(local_directory):
        match = pattern.match(file)
        if match:
            type_, node, date_part, time_part = match.groups()
            timestamp = f"{date_part}_{time_part}"
            key = f"{type_}_78E374R-{node}"

            if key not in latest_files or timestamp > latest_files[key]['timestamp']:
                latest_files[key] = {
                    'timestamp': timestamp,
                    'filename': file
                }

    # Удаление старых файлов
    for file in os.listdir(local_directory):
        match = pattern.match(file)
        if match:
            type_, node, date_part, time_part = match.groups()
            key = f"{type_}_78E374R-{node}"
            if key in latest_files and file != latest_files[key]['filename']:
                try:
                    os.remove(os.path.join(local_directory, file))
                    logging.info(f"Удален старый файл: {file}")
                except Exception as e:
                    logging.error(f"Не удалось удалить файл {file}: {e}")

    # Возвращает список самых свежих файлов
    return [os.path.join(local_directory, data['filename']) for data in latest_files.values()]

def worker(local_directory, update_interval):
    logging.info(f"Запуск рабочего потока для директории {local_directory}.")
    while True:
        try:
            logging.info(f"Поиск файлов в директории {local_directory}.")
            latest_files = get_latest_files(local_directory)
            if latest_files:
                for file_path in latest_files:
                    collect_metrics_from_file(file_path)
            else:
                logging.info("Файлы не найдены в локальной директории.")
        except Exception as e:
            logging.error(f"Ошибка в рабочем потоке: {e}")
        time.sleep(update_interval)

def main():
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    try:
        with open("config.toml", "rb") as toml_file:
            conf_dict = tomllib.load(toml_file)
    except FileNotFoundError:
        logging.error("Конфигурационный файл 'config.toml' не найден.")
        exit(1)
    except Exception as e:
        logging.error(f"Ошибка при чтении конфигурационного файла: {e}")
        exit(1)

    main_conf = conf_dict.get('main', {})
    local_directory = main_conf.get('LOCAL_DIR', "/app/iostats")
    update_interval = int(main_conf.get('IBM_METRIC_UPDATE_INTERVAL', 60))
    metric_port = int(main_conf.get('IBM_METRIC_PORT', 8000))

    logging.info(f"Запуск HTTP сервера на порту {metric_port}.")
    start_http_server(metric_port)

    threads = [threading.Thread(target=worker, args=(local_directory, update_interval))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()