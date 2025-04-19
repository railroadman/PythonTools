import re
import argparse
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates # Для форматирования дат на оси X

# --- Конфигурация ---
DEFAULT_LOG_FILE = 'system_monitor.log'
DEFAULT_OUTPUT_PNG = 'system_usage_plot.png'

# --- Парсинг аргументов командной строки ---
parser = argparse.ArgumentParser(description="Parse system monitor log file and create a usage plot.")
parser.add_argument(
    '--log-file',
    type=str,
    default=DEFAULT_LOG_FILE,
    help=f"Path to the input log file (default: {DEFAULT_LOG_FILE})"
)
parser.add_argument(
    '--output-png',
    type=str,
    default=DEFAULT_OUTPUT_PNG,
    help=f"Path to save the output PNG plot (default: {DEFAULT_OUTPUT_PNG})"
)
args = parser.parse_args()

# --- Функция парсинга лог-файла ---
def parse_log_file(log_filepath):
    """Читает лог-файл и извлекает временные метки, данные CPU и памяти."""
    timestamps = []
    cpu_percentages = []
    memory_percentages = []

    # Регулярное выражение для извлечения данных из строки лога
    # Формат: ГГГГ-ММ-ДД ЧЧ:ММ:СС - INFO - CPU Usage: XX.X% | Memory Usage: YY.Y% ...
    # Захватываем: (метка времени), (CPU %), (Memory %)
    log_pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - INFO - "
        r"CPU Usage: (\d+\.\d+)% \| "
        r"Memory Usage: (\d+\.\d+)%"
        # r".*" # Остальная часть строки нас не интересует для графика
    )

    print(f"Parsing log file: {log_filepath}...")
    try:
        with open(log_filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                match = log_pattern.search(line)
                if match:
                    try:
                        timestamp_str, cpu_str, memory_str = match.groups()
                        # Преобразуем строку времени в объект datetime
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        # Преобразуем строки процентов в числа float
                        cpu_percent = float(cpu_str)
                        memory_percent = float(memory_str)

                        timestamps.append(timestamp)
                        cpu_percentages.append(cpu_percent)
                        memory_percentages.append(memory_percent)
                    except ValueError as e:
                        print(f"Warning: Could not parse data on line {line_num}: {e}. Line: '{line.strip()}'")
                    except Exception as e:
                        print(f"Warning: An unexpected error occurred parsing line {line_num}: {e}. Line: '{line.strip()}'")
                # else:
                #     # Можно добавить вывод предупреждения о строках, не соответствующих шаблону, если нужно
                #     if line.strip() and "monitoring script started" not in line and "monitoring script finished" not in line and "Monitoring stopped" not in line:
                #          print(f"Warning: Line {line_num} did not match expected format: '{line.strip()}'")
    except FileNotFoundError:
        print(f"Error: Log file not found at '{log_filepath}'")
        return None, None, None
    except Exception as e:
        print(f"Error reading log file '{log_filepath}': {e}")
        return None, None, None

    print(f"Parsing complete. Found {len(timestamps)} valid data points.")
    return timestamps, cpu_percentages, memory_percentages

# --- Функция создания и сохранения графика ---
def create_plot(timestamps, cpu_percentages, memory_percentages, output_png_filepath):
    """Создает график CPU и Memory Usage и сохраняет его в PNG."""
    if not timestamps or not cpu_percentages or not memory_percentages:
        print("Error: No valid data found to plot.")
        return

    print(f"Creating plot and saving to {output_png_filepath}...")

    plt.figure(figsize=(15, 7)) # Задаем размер графика для лучшей читаемости

    # Строим графики
    plt.plot(timestamps, cpu_percentages, label='CPU Usage (%)', color='blue', linewidth=1.5)
    plt.plot(timestamps, memory_percentages, label='Memory Usage (%)', color='red', linewidth=1.5)

    # Настраиваем оси и заголовок
    plt.xlabel('Time')
    plt.ylabel('Usage (%)')
    plt.title('System CPU and Memory Usage Over Time')
    plt.ylim(0, 105) # Устанавливаем предел оси Y от 0 до 105% (чтобы видеть пики до 100%)
    plt.grid(True, linestyle='--', alpha=0.6) # Добавляем сетку
    plt.legend() # Показываем легенду (метки линий)

    # Улучшаем форматирование дат на оси X
    ax = plt.gca() # Получаем текущие оси
    # Устанавливаем основной форматтер и локатор
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10)) # Автоматический выбор интервалов дат
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M')) # Формат даты/времени

    plt.gcf().autofmt_xdate() # Автоматически наклоняем и выравниваем метки дат

    # Сохраняем график в файл PNG
    try:
        plt.savefig(output_png_filepath, dpi=150, bbox_inches='tight') # dpi - разрешение, bbox_inches - обрезка по содержимому
        print(f"Plot successfully saved to '{output_png_filepath}'")
    except Exception as e:
        print(f"Error saving plot to '{output_png_filepath}': {e}")

    # plt.show() # Раскомментируйте, если хотите также показать график на экране
    plt.close() # Закрываем фигуру, чтобы освободить память

# --- Основной блок выполнения ---
if __name__ == "__main__":
    timestamps, cpu_data, mem_data = parse_log_file(args.log_file)
    if timestamps: # Проверяем, что парсинг прошел успешно и есть данные
        create_plot(timestamps, cpu_data, mem_data, args.output_png)