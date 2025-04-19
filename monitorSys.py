import psutil
import time
import logging
from datetime import datetime
import argparse # For command-line arguments

# --- Configuration ---
DEFAULT_LOG_FILE = 'system_monitor.log'
DEFAULT_INTERVAL_SECONDS = 5 # Default check interval in seconds

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Monitor CPU and Memory usage and log it.")
parser.add_argument(
    '-i', '--interval',
    type=int,
    default=DEFAULT_INTERVAL_SECONDS,
    help=f"Monitoring interval in seconds (default: {DEFAULT_INTERVAL_SECONDS})"
)
parser.add_argument(
    '-l', '--logfile',
    type=str,
    default=DEFAULT_LOG_FILE,
    help=f"Path to the log file (default: {DEFAULT_LOG_FILE})"
)
parser.add_argument(
    '-v', '--verbose',
    action='store_true', # Sets verbose to True if flag is present
    help="Print logs to console in addition to the file"
)
args = parser.parse_args()

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('SystemMonitor')
logger.setLevel(logging.INFO) # Set the minimum logging level

# File Handler (always logs to file)
file_handler = logging.FileHandler(args.logfile)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

# Console Handler (only add if verbose mode is enabled)
if args.verbose:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

# --- Monitoring Function ---
def get_system_stats():
    """Retrieves current CPU and Memory statistics."""
    # Get CPU usage percentage (over the specified interval for accuracy)
    # The first call might return 0.0 or require a non-None interval.
    # Using interval=1 gives a measurement over 1 second.
    cpu_usage = psutil.cpu_percent(interval=1)

    # Get memory usage statistics
    memory_info = psutil.virtual_memory()
    memory_total_gb = memory_info.total / (1024**3) # Convert bytes to GB
    memory_available_gb = memory_info.available / (1024**3) # Convert bytes to GB
    memory_used_gb = memory_info.used / (1024**3) # Convert bytes to GB
    memory_usage_percent = memory_info.percent

    return {
        "cpu_percent": cpu_usage,
        "memory_percent": memory_usage_percent,
        "memory_total_gb": memory_total_gb,
        "memory_available_gb": memory_available_gb,
        "memory_used_gb": memory_used_gb,
    }

# --- Main Loop ---
def main():
    """Main monitoring loop."""
    logger.info(f"Starting system monitoring. Logging to '{args.logfile}'. Interval: {args.interval} seconds.")
    try:
        while True:
            stats = get_system_stats()

            # Format the log message
            log_message = (
                f"CPU Usage: {stats['cpu_percent']:.1f}% | "
                f"Memory Usage: {stats['memory_percent']:.1f}% "
                f"(Used: {stats['memory_used_gb']:.2f} GB, "
                f"Available: {stats['memory_available_gb']:.2f} GB, "
                f"Total: {stats['memory_total_gb']:.2f} GB)"
            )

            logger.info(log_message)

            # Wait for the next interval, accounting for the 1 second used by cpu_percent
            # Ensure sleep duration is non-negative
            sleep_time = max(0, args.interval - 1)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user (Ctrl+C).")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True) # Log traceback
    finally:
        logger.info("System monitoring script finished.")

if __name__ == "__main__":
    main()