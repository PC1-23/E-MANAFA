
"""Energy calculator for power rails data from Perfetto traces."""

from perfetto.trace_processor import TraceProcessor
from ..utils.Logger import log, LogSeverity


def calculate_energy_from_power_rails(trace_file):
    """Calculate energy consumption from power rails counters.
    
    Power rail counters report CUMULATIVE energy values (not instantaneous power),
    so we use simple subtraction: final_value - initial_value.
    """
    try:
        import os
        import time
        from perfetto.trace_processor import TraceProcessor

        log(f"Attempting to load trace file: {trace_file}", log_sev=LogSeverity.INFO)

        #check if file exists
        if not os.path.exists(trace_file):
            log(f"ERROR: Trace file does not exist: {trace_file}", log_sev=LogSeverity.ERROR)
            return None

        log(f"File exists, size: {os.path.getsize(trace_file)} bytes", log_sev=LogSeverity.INFO)

        #try to load TraceProcessor 
        tp = None
        try:
            log("Loading TraceProcessor (this may download the binary on first use)...", log_sev=LogSeverity.INFO)
            tp = TraceProcessor(trace=trace_file)
            log("TraceProcessor loaded successfully", log_sev=LogSeverity.INFO)
        except Exception as e:
            error_msg = str(e)
            if "failed to start" in error_msg.lower() or "download" in error_msg.lower():
                log("TraceProcessor binary download may have failed", log_sev=LogSeverity.ERROR)
                log("To fix this issue:", log_sev=LogSeverity.ERROR)
                log("  1. Check your internet connection", log_sev=LogSeverity.ERROR)
                log("  2. Run: python3 download_trace_processor.py", log_sev=LogSeverity.ERROR)
                log("  3. Or manually download from: https://get.perfetto.dev/trace_processor", log_sev=LogSeverity.ERROR)
            raise

        if tp is None:
            log("Failed to load TraceProcessor", log_sev=LogSeverity.ERROR)
            return None
        #load trace processor
        #tp = TraceProcessor(trace=trace_file)
        #log("TraceProcessor loaded successfully", log_sev=LogSeverity.INFO)
        
        #find all power rail counters
        query_rails = """
        SELECT DISTINCT t.name 
        FROM counter_track t
        WHERE t.name LIKE 'power.%'
        ORDER BY t.name
        """
        
        result_rails = tp.query(query_rails)
        rails = [row.name for row in result_rails]
        
        if not rails:
            log("No power rails found in trace", log_sev=LogSeverity.WARNING)
            return None
        
        log(f"Found {len(rails)} power rails", log_sev=LogSeverity.INFO)
        
        energy_by_rail = {}
        total_energy = 0.0
        
        for rail_name in rails:
            query = f"""
            SELECT c.ts, c.value 
            FROM counter c
            JOIN counter_track t ON c.track_id = t.id
            WHERE t.name = '{rail_name}'
            ORDER BY c.ts
            """
            
            result = tp.query(query)
            
            values = []
            for row in result:
                values.append(row.value)
            
            if len(values) >= 2:
                #simple subtraction for cumulative counters
                #values are in microwatt-seconds (µWs)
                energy_uws = values[-1] - values[0]
                
                #convert to Joules (1 µWs = 1e-6 J)
                energy_joules = energy_uws * 1e-6
                
                energy_by_rail[rail_name] = energy_joules
                total_energy += energy_joules
        
        result = {
            'total': total_energy,
            'by_rail': energy_by_rail
        }
        
        log(f"Total Energy: {total_energy:.2f} Joules", log_sev=LogSeverity.INFO)
        
        #show top 5 consumers
        sorted_rails = sorted(energy_by_rail.items(), key=lambda x: x[1], reverse=True)[:5]
        log("Top Power Consumers:", log_sev=LogSeverity.INFO)
        for rail, energy in sorted_rails:
            log(f"  {rail}: {energy:.2f} J", log_sev=LogSeverity.INFO)
        
        return result
        
    except Exception as e:
        import traceback
        log(f"Error calculating energy: {e}", log_sev=LogSeverity.ERROR)
        log(f"Traceback: {traceback.format_exc()}", log_sev=LogSeverity.ERROR)
        return None


def calculate_memory_stats(trace_file, app_package=None):
    """Calculate system memory statistics from Perfetto trace.
    
    Returns min, max, and average for system memory counters.
    """
    try:
        import os
        from perfetto.trace_processor import TraceProcessor

        log(f"Attempting to calculate memory stats from: {trace_file}", log_sev=LogSeverity.INFO)

        #check if file exists
        if not os.path.exists(trace_file):
            log(f"ERROR: Trace file does not exist: {trace_file}", log_sev=LogSeverity.ERROR)
            return None

        log(f"File exists, size: {os.path.getsize(trace_file)} bytes", log_sev=LogSeverity.INFO)

        #try to load TraceProcessor
        tp = None
        try:
            log("Loading TraceProcessor for memory stats...", log_sev=LogSeverity.INFO)
            tp = TraceProcessor(trace=trace_file)
            log("TraceProcessor loaded successfully", log_sev=LogSeverity.INFO)
        except Exception as e:
            error_msg = str(e)
            if "failed to start" in error_msg.lower() or "download" in error_msg.lower():
                log("TraceProcessor binary download may have failed", log_sev=LogSeverity.ERROR)
                log("To fix this issue:", log_sev=LogSeverity.ERROR)
                log("  1. Check your internet connection", log_sev=LogSeverity.ERROR)
                log("  2. Run: python3 download_trace_processor.py", log_sev=LogSeverity.ERROR)
                log("  3. Or manually download from: https://get.perfetto.dev/trace_processor", log_sev=LogSeverity.ERROR)
            raise

        if tp is None:
            log("Failed to load TraceProcessor", log_sev=LogSeverity.ERROR)
            return None
        
        #tp = TraceProcessor(trace=trace_file)
        #log("TraceProcessor loaded successfully for memory stats", log_sev=LogSeverity.INFO)
        
        #query for system memory counters
        query = """
        SELECT 
            t.name as counter_name,
            c.value as value_bytes
        FROM counter c
        JOIN counter_track t ON c.track_id = t.id
        WHERE t.name IN ('MemTotal', 'MemFree', 'MemAvailable', 
                         'Buffers', 'Cached', 'Active', 'Inactive')
        ORDER BY t.name, c.ts
        """
        
        result = tp.query(query)
        
        #organize data by counter name
        counters_data = {}
        for row in result:
            counter_name = row.counter_name
            if counter_name not in counters_data:
                counters_data[counter_name] = []
            counters_data[counter_name].append(row.value_bytes)
        
        if not counters_data:
            log("No system memory data found in trace", log_sev=LogSeverity.WARNING)
            return None
        
        log(f"Found memory data for {len(counters_data)} counters", log_sev=LogSeverity.INFO)
        
        #calculate statistics for each counter
        memory_stats = {}
        
        for counter_name, values in counters_data.items():
            if len(values) > 0:
                min_bytes = min(values)
                max_bytes = max(values)
                avg_bytes = sum(values) / len(values)
                
                memory_stats[counter_name] = {
                    'min_mb': min_bytes / (1024 * 1024),
                    'max_mb': max_bytes / (1024 * 1024),
                    'avg_mb': avg_bytes / (1024 * 1024),
                    'samples': len(values)
                }
        
        return memory_stats
        
    except Exception as e:
        import traceback
        log(f"Error calculating memory stats: {e}", log_sev=LogSeverity.ERROR)
        log(f"Traceback: {traceback.format_exc()}", log_sev=LogSeverity.ERROR)
        return None