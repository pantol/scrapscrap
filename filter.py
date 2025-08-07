#!/usr/bin/env python3
import json
import re
from pathlib import Path

def filter_threads_by_title(input_file, output_file=None, patterns=None, case_sensitive=False):
    """
    Filter threads from a JSON file based on title patterns and extract only titles and post contents.

    Args:
        input_file (str): Path to input JSON file.
        output_file (str, optional): Path to save the filtered output JSON.
        patterns (list of str, optional): Title patterns to match.
        case_sensitive (bool): Whether to match patterns case-sensitively.

    Returns:
        list: Filtered list of threads with only title and post content.
    """
    if patterns is None:
        patterns = ['xtb', 'trn']

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Detect the thread list
    if isinstance(data, dict):
        threads = data.get('threads', data.get('data', data.get('items', [])))
        if not threads and len(data) > 0:
            threads = list(data.values()) if not isinstance(list(data.values())[0], (str, int, float)) else [data]
    else:
        threads = data

    # Normalize patterns if needed
    patterns_to_check = patterns if case_sensitive else [p.lower() for p in patterns]

    filtered_threads = []

    for thread in threads:
        if not isinstance(thread, dict):
            continue

        title = thread.get('thread_title', thread.get('title', thread.get('name', '')))
        title_to_check = title if case_sensitive else title.lower()

        # Check if any pattern matches the title
        if any(pattern in title_to_check for pattern in patterns_to_check):
            filtered_thread = {
                "title": title,
                "posts": [{"content": post.get("content", "")} for post in thread.get("posts", [])]
            }
            filtered_threads.append(filtered_thread)

    # Save to output file if requested
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
        #'trn',
        'dig',
        #'1at',
        'kgn',
        'swm',
        #'mci'
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
