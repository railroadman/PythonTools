import psutil
import time
import argparse
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import defaultdict
import os # Для получения имени пользователя в некоторых случаях

# --- Конфигурация и аргументы ---
DEFAULT_DURATION_SECONDS = 30  # Длительность мониторинга по умолчанию
DEFAULT_INTERVAL_SECONDS = 3   # Интервал сбора данных по умолчанию
DEFAULT_TOP_N = 5              # Количество топ-процессов для отображения
DEFAULT_OUTPUT_PNG = 'top_processes_usage.png'

parser = argparse.ArgumentParser(description="Monitor per-process resource usage and plot the top consumers.")
parser.add_argument(
    '-d', '--duration',
    type=int,
    default=DEFAULT_DURATION_SECONDS,
    help=f"Total monitoring duration in seconds (default: {DEFAULT_DURATION_SECONDS})"
)
parser.add_argument(
    '-i', '--interval',
    type=float,
    default=DEFAULT_INTERVAL_SECONDS,
    help=f"Data collection interval in seconds (default: {DEFAULT_INTERVAL_SECONDS})"
)
parser.add_argument(
    '-n', '--top-n',
    type=int,
    default=DEFAULT_TOP_N,
    help=f"Number of top processes to show in the plot (default: {DEFAULT_TOP_N})"
)
parser.add_argument(
    '-o', '--output-png',
    type=str,
    default=DEFAULT_OUTPUT_PNG,
    help=f"Path to save the output PNG plot (default: {DEFAULT_OUTPUT_PNG})"
)
parser.add_argument(
    '--include-system-procs',
    action='store_true',
    help="Include system processes (like PID 0, often owned by 'system' or 'root')"
)

args = parser.parse_args()

# --- Сбор данных ---

def collect_process_data(duration_sec, interval_sec, include_system=False):
    """Собирает данные об использовании CPU и памяти процессами."""
    data = defaultdict(lambda: {'timestamps': [], 'cpu': [], 'mem_mb': [], 'name': None, 'username': None, 'cmdline': None})
    end_time = time.time() + duration_sec
    num_samples = 0

    print(f"Starting data collection for {duration_sec} seconds (interval: {interval_sec}s)...")

    # Первый вызов cpu_percent для инициализации (для некоторых систем)
    try:
        for proc in psutil.process_iter(['pid']):
             proc.cpu_percent(interval=None) # Initialize per-process cpu stats
    except Exception as e:
        print(f"Warning: Initial cpu_percent call failed for some processes: {e}")


    while time.time() < end_time:
        current_time = datetime.now()
        num_samples += 1
        print(f"\rCollecting sample {num_samples} at {current_time.strftime('%H:%M:%S')}...", end="")

        process_snapshot = {} # Временный словарь для текущего среза

        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'cmdline']):
            try:
                pid = proc.info['pid']

                # Пропускаем системные процессы, если не указан флаг
                # PID 0 (System Idle Process on Windows, kernel tasks on Linux) often has weird stats
                # Пропускаем процессы без имени или пользователя, если они не нужны
                if pid == 0 or (not include_system and (proc.info['username'] is None or proc.info['username'].lower() in ['system', 'root', 'local service', 'network service'])):
                     if pid != 0 and proc.info['name'] is not None and proc.info['name'].strip() != "": # Keep named system processes if needed later?
                        pass # Could add logic here if needed, for now skip fully
                     else:
                        continue # Skip PID 0 and unspecified system processes if flag is off

                # Получаем данные (cpu_percent может вернуть None при первом вызове)
                cpu = proc.info['cpu_percent']
                mem_rss_bytes = proc.info['memory_info'].rss # Resident Set Size
                mem_mb = mem_rss_bytes / (1024 * 1024) # Конвертируем в МБ

                # Пропускаем процессы с нулевым потреблением (опционально, для чистоты)
                # if cpu is None or (cpu == 0 and mem_mb < 0.1): # Порог можно настроить
                #     continue

                if cpu is None: cpu = 0.0 # Обрабатываем None от первого вызова

                # Сохраняем данные для этого PID в текущем срезе
                process_snapshot[pid] = {
                    'cpu': cpu,
                    'mem_mb': mem_mb,
                    'name': proc.info['name'],
                    'username': proc.info['username'],
                    'cmdline': ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else '' # Объединяем командную строку
                }

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Процесс мог завершиться или доступ запрещен
                continue
            except Exception as e:
                # Другие возможные ошибки psutil
                 # Не будем выводить для каждого процесса, чтобы не засорять лог
                 # print(f"\nWarning: Could not get info for PID {proc.pid if hasattr(proc, 'pid') else 'N/A'}: {e}")
                 pass

        # Добавляем данные из текущего среза в основной словарь `data`
        for pid, stats in process_snapshot.items():
             # Если это первый раз видим PID, сохраняем имя и пользователя
            if data[pid]['name'] is None:
                 data[pid]['name'] = stats['name']
                 data[pid]['username'] = stats['username']
                 data[pid]['cmdline'] = stats['cmdline']

            data[pid]['timestamps'].append(current_time)
            data[pid]['cpu'].append(stats['cpu'])
            data[pid]['mem_mb'].append(stats['mem_mb'])


        # Ждем до следующего интервала
        time.sleep(interval_sec)

    print(f"\nData collection finished. Collected {num_samples} samples for {len(data)} processes.")
    return data

# --- Анализ данных и определение Топ-N ---

def analyze_data(data, top_n):
    """Анализирует собранные данные и определяет топ N потребителей."""
    if not data:
        return None, None, None

    process_summary = defaultdict(lambda: {'total_cpu': 0, 'total_mem': 0, 'count': 0, 'name': None, 'username': None, 'cmdline': None, 'pid': None})

    # Суммируем показатели для каждого PID
    for pid, stats in data.items():
        if not stats['cpu'] or not stats['mem_mb']: # Пропускаем, если нет данных
             continue
        process_summary[pid]['total_cpu'] = sum(stats['cpu'])
        process_summary[pid]['total_mem'] = sum(stats['mem_mb'])
        process_summary[pid]['count'] = len(stats['timestamps'])
        process_summary[pid]['name'] = stats['name']
        process_summary[pid]['username'] = stats['username']
        process_summary[pid]['cmdline'] = stats['cmdline']
        process_summary[pid]['pid'] = pid # Сохраняем PID для идентификации

    # Рассчитываем средние значения и создаем список для сортировки
    average_stats = []
    for pid, summary in process_summary.items():
        if summary['count'] > 0:
            avg_cpu = summary['total_cpu'] / summary['count']
            avg_mem = summary['total_mem'] / summary['count']
            # Создаем уникальный идентификатор процесса (имя + cmdline или PID)
            proc_id_str = f"{summary['name']} ({pid})"
            # Можно усложнить, если cmdline нужен для различения одинаковых имен:
            # cmd_short = (summary['cmdline'][:30] + '...') if summary['cmdline'] and len(summary['cmdline']) > 30 else summary['cmdline']
            # proc_id_str = f"{summary['name']} [{cmd_short}] ({pid})"

            average_stats.append({
                'pid': pid,
                'id_str': proc_id_str,
                'avg_cpu': avg_cpu,
                'avg_mem': avg_mem
            })

    # Сортируем процессы
    top_cpu_consumers = sorted(average_stats, key=lambda x: x['avg_cpu'], reverse=True)
    top_mem_consumers = sorted(average_stats, key=lambda x: x['avg_mem'], reverse=True)

    # Выбираем топ N PIDs для каждого ресурса
    top_cpu_pids = [p['pid'] for p in top_cpu_consumers[:top_n]]
    top_mem_pids = [p['pid'] for p in top_mem_consumers[:top_n]]

    # Получаем их идентификаторы для легенды
    top_cpu_ids = {p['pid']: p['id_str'] for p in top_cpu_consumers[:top_n]}
    top_mem_ids = {p['pid']: p['id_str'] for p in top_mem_consumers[:top_n]}


    print("\nTop CPU Consumers (Average):")
    for p in top_cpu_consumers[:top_n]:
        print(f"  - {p['id_str']}: {p['avg_cpu']:.2f}%")

    print("\nTop Memory Consumers (Average RSS):")
    for p in top_mem_consumers[:top_n]:
        print(f"  - {p['id_str']}: {p['avg_mem']:.2f} MB")


    return top_cpu_pids, top_mem_pids, top_cpu_ids, top_mem_ids


# --- Построение графика ---

def create_process_plot(data, top_cpu_pids, top_mem_pids, top_cpu_ids, top_mem_ids, output_png_filepath):
    """Создает график с двумя под-графиками для CPU и Памяти топ-N процессов."""
    if not top_cpu_pids and not top_mem_pids:
        print("Error: No top consumers identified to plot.")
        return

    print(f"\nCreating plot and saving to {output_png_filepath}...")

    # Создаем фигуру с двумя под-графиками (один над другим)
    fig, axes = plt.subplots(2, 1, figsize=(15, 12), sharex=True) # sharex=True связывает оси X

    # --- График CPU ---
    ax_cpu = axes[0]
    for pid in top_cpu_pids:
        if pid in data and data[pid]['timestamps']:
            label = top_cpu_ids.get(pid, f"PID {pid}") # Используем сохраненный ID
            ax_cpu.plot(data[pid]['timestamps'], data[pid]['cpu'], label=label, linewidth=1.5, marker='.', markersize=4, alpha=0.8)

    ax_cpu.set_title(f'Top {len(top_cpu_pids)} CPU Consuming Processes (Usage %)')
    ax_cpu.set_ylabel('CPU Usage (%)')
    ax_cpu.legend(loc='upper left', fontsize='small')
    ax_cpu.grid(True, linestyle='--', alpha=0.6)
    ax_cpu.set_ylim(bottom=0) # Начинаем ось Y с 0

    # --- График Памяти (RSS) ---
    ax_mem = axes[1]
    for pid in top_mem_pids:
         if pid in data and data[pid]['timestamps']:
            label = top_mem_ids.get(pid, f"PID {pid}") # Используем сохраненный ID
            ax_mem.plot(data[pid]['timestamps'], data[pid]['mem_mb'], label=label, linewidth=1.5, marker='.', markersize=4, alpha=0.8)

    ax_mem.set_title(f'Top {len(top_mem_pids)} Memory Consuming Processes (RSS MB)')
    ax_mem.set_ylabel('Memory Usage (MB)')
    ax_mem.legend(loc='upper left', fontsize='small')
    ax_mem.grid(True, linestyle='--', alpha=0.6)
    ax_mem.set_ylim(bottom=0) # Начинаем ось Y с 0

    # Настраиваем общую ось X
    ax_mem.set_xlabel('Time')
    ax_mem.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10))
    ax_mem.xaxis.set_major_formatter(mdates.DateFormatter('%d %b %H:%M:%S')) # Формат как в предыдущем запросе + секунды

    fig.autofmt_xdate() # Автоматический наклон меток времени
    plt.tight_layout(rect=[0, 0.03, 1, 0.98]) # Улучшаем расположение, оставляем место для заголовка фигуры

    # Общий заголовок (опционально)
    # fig.suptitle('System Resource Usage by Top Processes', fontsize=16)

    # Сохраняем график
    try:
        plt.savefig(output_png_filepath, dpi=150)
        print(f"Plot successfully saved to '{output_png_filepath}'")
    except Exception as e:
        print(f"Error saving plot to '{output_png_filepath}': {e}")

    # plt.show() # Раскомментируйте для отображения
    plt.close(fig) # Закрываем фигуру

# --- Основной блок ---
if __name__ == "__main__":
    collected_data = collect_process_data(args.duration, args.interval, args.include_system_procs)
    if collected_data:
        top_cpu_pids, top_mem_pids, top_cpu_ids, top_mem_ids = analyze_data(collected_data, args.top_n)
        if top_cpu_pids or top_mem_pids: # Если есть хотя бы один список топ-процессов
             create_process_plot(collected_data, top_cpu_pids, top_mem_pids, top_cpu_ids, top_mem_ids, args.output_png)
        else:
            print("Could not identify any top processes based on collected data.")
    else:
        print("No data was collected.")