#!/usr/bin/env python3
import json
import re
from pathlib import Path

def filter_threads_by_title(input_file, output_file=None, patterns=None, case_sensitive=False):
    """
    Filter threads from JSON file based on title patterns.
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output JSON file (optional)
        patterns: List of patterns to match in thread titles
        case_sensitive: Whether to use case-sensitive matching
    
    Returns:
        List of filtered threads
    """
    
    # Default patterns if none provided
    if patterns is None:
        patterns = ['xtb', 'trn']  # Add more patterns as needed
    
    # Read the JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check if data is a list or dict with threads
    if isinstance(data, dict):
        # If it's a dict, look for common keys that might contain thread list
        threads = data.get('threads', data.get('data', data.get('items', [])))
        if not threads and len(data) > 0:
            # Assume the dict values are the threads
            threads = list(data.values()) if not isinstance(list(data.values())[0], (str, int, float)) else [data]
    else:
        threads = data
    
    # Filter threads based on patterns
    filtered_threads = []
    
    for thread in threads:
        # Get thread title - handle different possible structures
        if isinstance(thread, dict):
            title = thread.get('thread_title', thread.get('title', thread.get('name', '')))
        else:
            continue
        
        # Check if any pattern matches the title
        title_to_check = title if case_sensitive else title.lower()
        patterns_to_check = patterns if case_sensitive else [p.lower() for p in patterns]
        
        # Check for matches
        for pattern in patterns_to_check:
            # You can use different matching strategies:
            
            # Strategy 1: Pattern is anywhere in the title
            if pattern in title_to_check:
                filtered_threads.append(thread)
                break
            
            # Strategy 2: Pattern matches as a whole word (uncomment if needed)
            # if re.search(r'\b' + re.escape(pattern) + r'\b', title_to_check):
            #     filtered_threads.append(thread)
            #     break
            
            # Strategy 3: Pattern matches at the beginning (uncomment if needed)
            # if title_to_check.startswith(pattern):
            #     filtered_threads.append(thread)
            #     break
    
    # Save to output file if specified
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_threads, f, indent=2, ensure_ascii=False)
        print(f"Filtered {len(filtered_threads)} threads saved to {output_file}")
    
    return filtered_threads


def main():
    # Configuration
    INPUT_FILE = 'scraped_data.json'  # Change to your input file name
    OUTPUT_FILE = 'filtered_threads.json'  # Output file name
    
    # Define the patterns you want to match
    # You can add more patterns or load them from a file
    PATTERNS = [
        'xtb',
        'trn',
        # Add more patterns here
    ]
    
    # Advanced: Use regex patterns (uncomment to use)
    # REGEX_PATTERNS = [
    #     r'^xtb',  # Starts with 'xtb'
    #     r'trn\d+',  # 'trn' followed by numbers
    #     r'\[xtb\]',  # '[xtb]' in brackets
    # ]
    
    try:
        # Filter threads
        filtered = filter_threads_by_title(
            input_file=INPUT_FILE,
            output_file=OUTPUT_FILE,
            patterns=PATTERNS,
            case_sensitive=False  # Set to True for case-sensitive matching
        )
        
        # Print summary
        print(f"\nFound {len(filtered)} matching threads:")
        print("-" * 50)
        
        # Display first few results
        for i, thread in enumerate(filtered[:5], 1):
            title = thread.get('thread_title', thread.get('title', 'No title'))
            print(f"{i}. {title}")
        
        if len(filtered) > 5:
            print(f"... and {len(filtered) - 5} more threads")
        
    except FileNotFoundError:
        print(f"Error: File '{INPUT_FILE}' not found!")
        print("Please make sure the file exists in the current directory.")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file - {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


# Additional utility function for regex-based filtering
def filter_threads_regex(input_file, output_file=None, regex_patterns=None):
    """
    Filter threads using regular expressions for more complex pattern matching.
    """
    if regex_patterns is None:
        regex_patterns = [r'xtb', r'trn']
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Compile regex patterns
    compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in regex_patterns]
    
    threads = data if isinstance(data, list) else data.get('threads', [])
    filtered_threads = []
    
    for thread in threads:
        title = thread.get('thread_title', '')
        
        # Check if any regex pattern matches
        if any(pattern.search(title) for pattern in compiled_patterns):
            filtered_threads.append(thread)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_threads, f, indent=2, ensure_ascii=False)
    
    return filtered_threads


if __name__ == "__main__":
    main()