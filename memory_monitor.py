"""
Memory Monitoring & Optimization Script for Pothole Detection System
Use this to monitor memory usage and identify bottlenecks
"""

import psutil
import json
import time
from pathlib import Path
from datetime import datetime

class MemoryMonitor:
    def __init__(self, log_file='memory_usage.json'):
        self.log_file = Path(log_file)
        self.process = psutil.Process()
        self.start_time = time.time()
        self.measurements = []
    
    def get_memory_info(self):
        """Get current memory usage info"""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)
        num_threads = self.process.num_threads()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'rss_mb': round(memory_info.rss / 1024 / 1024, 2),
            'vms_mb': round(memory_info.vms / 1024 / 1024, 2),
            'percent': round(self.process.memory_percent(), 2),
            'cpu_percent': cpu_percent,
            'num_threads': num_threads,
            'elapsed_seconds': round(time.time() - self.start_time, 2)
        }
    
    def log_measurement(self, operation_name):
        """Log a memory measurement"""
        info = self.get_memory_info()
        info['operation'] = operation_name
        self.measurements.append(info)
        
        print(f"\n📊 [{operation_name}] Memory: {info['rss_mb']} MB | "
              f"CPU: {info['cpu_percent']}% | Threads: {info['num_threads']}")
        
        return info
    
    def save_log(self):
        """Save measurements to JSON log"""
        with open(self.log_file, 'w') as f:
            json.dump(self.measurements, f, indent=2)
        print(f"\n✓ Memory log saved to {self.log_file}")
    
    def print_summary(self):
        """Print summary statistics"""
        if not self.measurements:
            print("No measurements recorded")
            return
        
        rss_values = [m['rss_mb'] for m in self.measurements]
        
        print("\n" + "="*60)
        print("MEMORY USAGE SUMMARY")
        print("="*60)
        print(f"Initial Memory:  {rss_values[0]:.2f} MB")
        print(f"Peak Memory:     {max(rss_values):.2f} MB")
        print(f"Final Memory:    {rss_values[-1]:.2f} MB")
        print(f"Memory Change:   {rss_values[-1] - rss_values[0]:+.2f} MB")
        print(f"Total Runtime:   {self.measurements[-1]['elapsed_seconds']:.2f}s")
        print("="*60 + "\n")


def test_image_processing(monitor):
    """Test image processing memory usage"""
    from app import process_image
    from pathlib import Path
    
    # Create dummy image or use existing
    test_image = Path("test_image.jpg")
    
    if test_image.exists():
        print("\nTesting image processing...")
        monitor.log_measurement("Before Image Processing")
        
        result, error = process_image(str(test_image))
        
        monitor.log_measurement("After Image Processing")
        
        if error:
            print(f"Error: {error}")
        else:
            print(f"✓ Detected {result['report']['pothole_count']} potholes")


def test_video_processing(monitor):
    """Test video processing memory usage"""
    from app import process_video
    from pathlib import Path
    
    test_video = Path("test_video.mp4")
    
    if test_video.exists():
        print("\nTesting video processing...")
        monitor.log_measurement("Before Video Processing")
        
        result, error = process_video(str(test_video))
        
        monitor.log_measurement("After Video Processing")
        
        if error:
            print(f"Error: {error}")
        else:
            print(f"✓ Detected {result['report']['total_potholes_detected']} potholes across "
                  f"{result['report']['unique_potholes']} unique locations")


def test_garbage_collection():
    """Test garbage collection efficiency"""
    import gc
    
    print("\n" + "="*60)
    print("GARBAGE COLLECTION STATS")
    print("="*60)
    
    # Get collection stats
    stats = gc.get_stats()
    for i, gen_stats in enumerate(stats):
        print(f"\nGeneration {i}:")
        print(f"  Collections: {gen_stats.get('collections', 0)}")
        print(f"  Collected: {gen_stats.get('collected', 0)}")
        print(f"  Uncollectable: {gen_stats.get('uncollectable', 0)}")
    
    print("\n" + "="*60 + "\n")


def continuous_monitor(duration=60):
    """Monitor memory usage continuously for specified duration"""
    monitor = MemoryMonitor()
    
    print(f"\nMonitoring for {duration} seconds...")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            info = monitor.get_memory_info()
            
            # Print in a compact format
            bar_length = int(info['percent'] / 2)  # Max 50 chars
            bar = "█" * bar_length + "░" * (50 - bar_length)
            
            print(f"\r[{bar}] {info['rss_mb']:6.1f} MB | "
                  f"CPU: {info['cpu_percent']:5.1f}% | "
                  f"Threads: {info['num_threads']:3d}", end="")
            
            monitor.measurements.append(info)
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")
        monitor.save_log()
        monitor.print_summary()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "monitor"
    
    if mode == "monitor":
        continuous_monitor()
    elif mode == "gc":
        test_garbage_collection()
    else:
        print("Usage: python memory_monitor.py [monitor|gc]")
