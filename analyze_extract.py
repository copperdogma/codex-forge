import json
from datetime import datetime

def parse_ts(ts_str):
    if not ts_str: return 0
    # 2025-11-24T19:57:22.700749Z
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.timestamp()
    except:
        return 0

events = []
with open('output/runs/deathtrap-ocr-full/pipeline_events.jsonl', 'r') as f:
    for line in f:
        try:
            evt = json.loads(line)
            if evt.get('stage') == 'extract':
                events.append(evt)
        except:
            pass

events.sort(key=lambda x: x.get('timestamp', ''))

print(f"Found {len(events)} events for 'extract'")
print(f"Event 113: {events[113]}")
print(f"Event 114: {events[114]}")


last_ts = 0
session_start = 0
total_duration = 0
run_count = 0
gaps = []

GAP_THRESHOLD_RESTART = 5 # 5s
GAP_THRESHOLD_TIMEOUT = 12 * 60 * 60 # 12h

for i, evt in enumerate(events):
    ts = parse_ts(evt.get('timestamp'))
    if not ts: continue
    
    is_new_session = False
    
    if last_ts:
        gap = ts - last_ts
        last_status = events[i-1].get('status')
        
        if last_status in ['done', 'failed']:
            if gap > GAP_THRESHOLD_RESTART:
                is_new_session = True
                print(f"New session (restart): gap {gap}s at index {i}, last_status {last_status}")
        else:
            if gap > GAP_THRESHOLD_TIMEOUT:
                is_new_session = True
                print(f"New session (timeout): gap {gap}s at index {i}, last_status {last_status}")

    if is_new_session:
        if session_start:
            total_duration += (last_ts - session_start)
            run_count += 1
            session_start = 0
            
    if not session_start:
        session_start = ts
        
    if i == len(events) - 1:
        if session_start:
            total_duration += (ts - session_start)
            run_count += 1

    last_ts = ts

print(f"Total Duration: {total_duration}s")
print(f"Run Count: {run_count}")
