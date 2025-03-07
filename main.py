from collections import deque
from datetime import datetime, timezone

def parse_iso8601_to_epoch(iso8601_str):
    """Convert timestamp from ISO-8601 format to epoch time."""
    dt = datetime.fromisoformat(iso8601_str.replace('Z', '+00:00'))
    return int(dt.timestamp())

def is_request_allowed(timestamps, current_timestamp, R):
    """Check if the request is allowed based on the sliding window algorithm."""
    # Remove timestamps older than current_time - 3600
    while timestamps and timestamps[0] < current_timestamp - 3600:
        timestamps.popleft()
    
    # Check the number of requests remaining in the queue
    if len(timestamps) >= R:
        return False
    else:
        timestamps.append(current_timestamp)
        return True

def rate_limiting(requests, R):
    """Main function to perform rate limiting."""
    results = []
    timestamps = deque()
    
    for iso8601_str in requests:
        current_timestamp = parse_iso8601_to_epoch(iso8601_str)
        allowed = is_request_allowed(timestamps, current_timestamp, R)
        results.append(allowed)
    
    return results

# Read input from file
if __name__ == "__main__":
    input_file_path = 'test/input1.txt'
    output_file_path = 'output.txt'
    
    with open(input_file_path, 'r') as file:
        # Read the number of requests and rate limit
        N, R = map(int, file.readline().split())
        
        # Read the timestamps of the requests
        requests = [file.readline().strip() for _ in range(N)]
    
    # Perform rate limiting
    results = rate_limiting(requests, R)
    
    # Write results to file
    with open(output_file_path, 'w') as file:
        for result in results:
            file.write("true\n" if result else "false\n")