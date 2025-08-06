#!/usr/bin/env python3 
import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import time
import re
from urllib.parse import urljoin, urlparse
import sys

# Load environment variables
load_dotenv()
FORUM_USERNAME = os.getenv("FORUM_USERNAME")
FORUM_PASSWORD = os.getenv("FORUM_PASSWORD")

# Threads to skip - administrative/general discussion threads
SKIP_THREAD_TITLES = [
    "SPÓŁKA DO ANALIZY",
    "DYSKUSJA OGÓLNA, MAKRO, WYDARZENIA",
    "KOMUNIKATY ADMINÓW, INFO O NOWYCH ANALIZACH"
]

def load_config():
    """Loads configuration."""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "base_url": "https://portalanaliz.pl/forum/",
            "delay_between_requests_sec": 2,
            "filters": {"keywords": [], "target_users": []}
        }

def load_state():
    """Load last run timestamp and check if this is initial run."""
    try:
        with open("state.json", "r", encoding="utf-8") as f:
            state = json.load(f)
            # Check if this is an initial run
            is_initial = state.get("is_initial_run", False)
            last_timestamp = datetime.fromisoformat(state["last_scrape_timestamp_utc"])
            return last_timestamp, is_initial
    except:
        # First run - scrape everything
        print("📌 No previous state found - this will be an initial full scrape")
        return datetime(2000, 1, 1, tzinfo=timezone.utc), True

def save_state(timestamp, is_initial=False):
    """Save current timestamp and run type."""
    state = {
        "last_scrape_timestamp_utc": timestamp.isoformat(),
        "is_initial_run": is_initial
    }
    with open("state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

def update_output_file(new_threads_data):
    """Save scraped data."""
    output_file = "scraped_data.json"
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {"scraped_timestamp_utc": "", "source_forum": "PortalAnaliz.pl", "threads": []}

    existing_threads = {thread['thread_id']: thread for thread in data['threads']}

    for thread_id, new_thread in new_threads_data.items():
        if thread_id in existing_threads:
            # Merge posts - avoid duplicates
            existing_post_ids = {post['post_id'] for post in existing_threads[thread_id]['posts']}
            for new_post in new_thread['posts']:
                if new_post['post_id'] not in existing_post_ids:
                    existing_threads[thread_id]['posts'].append(new_post)
            # Update thread title if changed
            existing_threads[thread_id]['thread_title'] = new_thread['thread_title']
        else:
            data['threads'].append(new_thread)

    data['scraped_timestamp_utc'] = datetime.now(timezone.utc).isoformat()
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"✅ Saved data to {output_file}")

def create_session():
    """Create session with proper headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'identity',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    return session

def login_to_forum(session):
    """Enhanced login with better phpBB compatibility."""
    if not FORUM_USERNAME or not FORUM_PASSWORD:
        print("❌ Missing credentials in .env file")
        return False

    print("🔐 Logging into forum...")
    
    try:
        # Step 1: First visit the main page to establish session
        print("🌐 Establishing session...")
        main_page = session.get("https://portalanaliz.pl/forum/")
        main_page.raise_for_status()
        time.sleep(1)
        
        # Step 2: Get the login page
        login_url = "https://portalanaliz.pl/forum/ucp.php?mode=login"
        print(f"📄 Getting login page: {login_url}")
        
        response = session.get(login_url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the login form
        login_form = soup.find('form', {'id': 'login'}) or soup.find('form', method='post')
        
        if not login_form:
            print("❌ No login form found")
            with open('login_page_debug.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("🔍 Debug info saved to login_page_debug.html")
            return False
        
        # Step 3: Extract ALL hidden fields from the form
        hidden_fields = {}
        for hidden_input in login_form.find_all('input', {'type': 'hidden'}):
            name = hidden_input.get('name')
            value = hidden_input.get('value', '')
            if name:
                hidden_fields[name] = value
                if len(value) > 20:
                    print(f"  📝 Found hidden field: {name} = {value[:20]}...")
                else:
                    print(f"  📝 Found hidden field: {name} = {value}")
        
        # Step 4: Build the form action URL
        form_action = login_form.get('action', '')
        if form_action:
            submit_url = urljoin("https://portalanaliz.pl/forum/", form_action)
        else:
            submit_url = login_url
        
        print(f"📤 Form action URL: {submit_url}")
        
        # Step 5: Prepare login data with ALL fields
        login_data = {
            'username': FORUM_USERNAME,
            'password': FORUM_PASSWORD,
            'autologin': 'on',
            'viewonline': 'on',
            'login': 'Zaloguj'
        }
        
        # Add all hidden fields
        login_data.update(hidden_fields)
        
        if 'redirect' not in login_data:
            login_data['redirect'] = 'index.php'
        
        print(f"📊 Submitting {len(login_data)} fields to login...")
        
        # Step 6: Submit login with proper headers
        login_headers = {
            'Referer': login_url,
            'Origin': 'https://portalanaliz.pl',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        login_response = session.post(
            submit_url, 
            data=login_data, 
            headers=login_headers,
            allow_redirects=True,
            timeout=30
        )
        login_response.raise_for_status()
        
        print(f"📨 Response status: {login_response.status_code}")
        print(f"🌐 Final URL: {login_response.url}")
        
        # Step 7: Check for login success
        login_soup = BeautifulSoup(login_response.text, 'html.parser')
        
        # Check for error messages
        error_div = login_soup.find('div', class_='error')
        if error_div:
            error_text = error_div.get_text(strip=True)
            print(f"❌ Login error: {error_text}")
            
            with open('login_response_debug.html', 'w', encoding='utf-8') as f:
                f.write(login_response.text)
            print("🔍 Debug info saved to login_response_debug.html")
            
            if "nieprawidłowy" in error_text.lower() or "invalid" in error_text.lower():
                print("⚠️  Form validation failed - check credentials and retry later")
            
            return False
        
        # Check for success indicators
        success_indicators = [
            'wyloguj' in login_response.text.lower(),
            'logout' in login_response.text.lower(),
            'panel użytkownika' in login_response.text.lower(),
            FORUM_USERNAME.lower() in login_response.text.lower()
        ]
        
        if any(success_indicators):
            print("✅ Login appears successful!")
        else:
            print("⚠️  Login status unclear, testing access...")
        
        # Step 8: Test actual forum access
        time.sleep(2)
        print("🧪 Testing forum access...")
        
        test_url = "https://portalanaliz.pl/forum/viewforum.php?f=3"
        test_response = session.get(test_url, timeout=10)
        
        if test_response.status_code == 200:
            test_text = test_response.text.lower()
            
            if 'viewtopic.php' in test_text and 'topictitle' in test_text:
                print("🎉 LOGIN SUCCESSFUL! Can access forum content.")
                return True
            elif 'musisz się zalogować' in test_text or 'you must login' in test_text:
                print("❌ Still seeing login requirements")
                return False
            else:
                if re.search(r'<a[^>]*class="topictitle"', test_response.text):
                    print("✅ Can see thread titles - login successful!")
                    return True
                else:
                    print("⚠️  Cannot confirm login status, attempting to continue...")
                    return True
        else:
            print(f"❌ Cannot access forum (status: {test_response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"💥 Network error during login: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error during login: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_gpw_threads(session):
    """Get all threads from GPW section across all pages."""
    print("🔍 Getting GPW section threads...")

    base_url = "https://portalanaliz.pl/forum/"
    threads = []
    seen_thread_ids = set()
    page_num = 0
    
    # Start with the first page
    current_url = urljoin(base_url, "viewforum.php?f=3")

    while current_url:
        page_num += 1
        print(f"📖 Processing page {page_num}: {current_url}")
        
        try:
            response = session.get(current_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Multiple selectors for thread links
            thread_links = []
            for selector in ['a.topictitle', 'dt a.topictitle', 'h3 a.topictitle']:
                thread_links = soup.select(selector)
                if thread_links:
                    break
            
            if not thread_links:
                thread_links = soup.find_all('a', href=re.compile(r'viewtopic\.php\?.*t=\d+'))

            print(f"  📋 Found {len(thread_links)} potential thread links")

            threads_on_page = 0
            for link in thread_links:
                href = link.get('href', '')
                title = link.get_text(strip=True)

                # Skip if no href or title
                if not href or not title:
                    continue

                # Skip navigation links
                if title in ['Następny', 'Poprzedni', 'Next', 'Previous']:
                    continue
                
                # Skip threads based on title
                should_skip = False
                for skip_title in SKIP_THREAD_TITLES:
                    if skip_title.upper() in title.upper():
                        print(f"  ⏭️  Skipping thread: {title}")
                        should_skip = True
                        break
                
                if should_skip:
                    continue

                # Build full URL
                full_url = urljoin(base_url, href)

                # Extract thread ID
                thread_match = re.search(r't=(\d+)', href)
                if thread_match:
                    thread_id = thread_match.group(1)

                    # Avoid duplicates
                    if thread_id not in seen_thread_ids:
                        threads.append({
                            'id': thread_id,
                            'title': title,
                            'url': full_url
                        })
                        seen_thread_ids.add(thread_id)
                        threads_on_page += 1

            print(f"  ✅ Added {threads_on_page} valid threads from this page")

            # Look for next page
            current_url = None
            
            # Method 1: Look for "Next" arrow
            next_li = soup.find('li', class_='arrow next')
            if next_li and next_li.a and 'href' in next_li.a.attrs:
                href = next_li.a['href']
                current_url = urljoin(base_url, href)
            else:
                # Method 2: Look for pagination links
                pagination = soup.find('div', class_='pagination') or soup.find('ul', class_='pagination')
                if pagination:
                    # Find "Następna" or next page number
                    next_link = pagination.find('a', text=re.compile(r'Następ|Next|»'))
                    if not next_link:
                        # Try to find numbered pages
                        current_page = pagination.find('li', class_='active') or pagination.find('strong')
                        if current_page:
                            try:
                                current_num = int(current_page.get_text().strip())
                                next_link = pagination.find('a', text=str(current_num + 1))
                            except:
                                pass
                    
                    if next_link and 'href' in next_link.attrs:
                        href = next_link['href']
                        current_url = urljoin(base_url, href)

            if current_url:
                print(f"  ➡️  Found next page: {current_url}")
                time.sleep(1)  # Small delay between pages
            else:
                print("  ✅ No more pages found")

        except Exception as e:
            print(f"💥 Error processing page {current_url}: {e}")
            break

    print(f"✅ Found {len(threads)} unique threads across all pages (excluding skipped threads)")
    return threads

def parse_date(date_string):
    """Parse Polish date formats with better handling."""
    if not date_string:
        return None
    
    # Clean the string
    date_string = date_string.strip()
    
    # Polish month mapping
    polish_months = {
        'stycznia': '01', 'styczeń': '01', 'sty': '01',
        'lutego': '02', 'luty': '02', 'lut': '02',
        'marca': '03', 'marzec': '03', 'mar': '03',
        'kwietnia': '04', 'kwiecień': '04', 'kwi': '04',
        'maja': '05', 'maj': '05',
        'czerwca': '06', 'czerwiec': '06', 'cze': '06',
        'lipca': '07', 'lipiec': '07', 'lip': '07',
        'sierpnia': '08', 'sierpień': '08', 'sie': '08',
        'września': '09', 'wrzesień': '09', 'wrz': '09',
        'października': '10', 'październik': '10', 'paź': '10',
        'listopada': '11', 'listopad': '11', 'lis': '11',
        'grudnia': '12', 'grudzień': '12', 'gru': '12'
    }
    
    # Try to parse Polish format (e.g., "05 sierpnia 2024, 14:30")
    polish_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4}),?\s+(\d{1,2}):(\d{2})', date_string)
    if polish_match:
        day, month_name, year, hour, minute = polish_match.groups()
        month_num = polish_months.get(month_name.lower())
        if month_num:
            try:
                return datetime(int(year), int(month_num), int(day), 
                              int(hour), int(minute), tzinfo=timezone.utc)
            except:
                pass
    
    # Try standard formats
    formats = [
        '%d.%m.%Y %H:%M',
        '%d-%m-%Y %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y %H:%M'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt).replace(tzinfo=timezone.utc)
        except:
            continue
    
    return None

def scrape_thread(session, thread_url, thread_id, last_timestamp, is_initial_run=False):
    """Scrape posts from thread across all pages."""
    posts = []
    current_url = thread_url
    page_num = 0
    
    while current_url:
        page_num += 1
        try:
            response = session.get(current_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find posts - phpBB3 structure
            post_elements = soup.select('div.post') or soup.select('div[id^="p"]')
            
            if page_num == 1:
                print(f"      📄 Processing page {page_num} - found {len(post_elements)} posts")
            else:
                print(f"      📄 Page {page_num} - found {len(post_elements)} posts")
            
            posts_on_page = 0
            
            for post_elem in post_elements:
                try:
                    # Get post ID
                    post_id_attr = post_elem.get('id', '')
                    if post_id_attr.startswith('p'):
                        post_id = post_id_attr[1:]
                    else:
                        anchor = post_elem.find('a', {'name': True})
                        post_id = anchor.get('name', f"post_{len(posts)+1}") if anchor else f"post_{len(posts)+1}"
                    
                    # Get author
                    author = "Unknown"
                    author_selectors = [
                        'dl.postprofile dt strong',
                        'dl.postprofile dt a',
                        'p.author strong',
                        'p.author a'
                    ]
                    
                    for selector in author_selectors:
                        author_elem = post_elem.select_one(selector)
                        if author_elem:
                            author = author_elem.get_text(strip=True)
                            break
                    
                    # Get content
                    content = ""
                    content_elem = post_elem.select_one('div.content')
                    if content_elem:
                        # Remove quotes if present
                        for quote in content_elem.select('blockquote'):
                            quote.decompose()
                        content = content_elem.get_text(strip=True)
                    
                    # Get post date
                    post_date = None
                    date_elem = post_elem.select_one('p.author')
                    if date_elem:
                        date_text = date_elem.get_text()
                        date_match = re.search(r'»\s*(.+?)(?:\s*$|\s*\n)', date_text)
                        if date_match:
                            date_str = date_match.group(1).strip()
                            post_date = parse_date(date_str)
                    
                    # Only add if we have minimum required data
                    if post_id and author != "Unknown" and content and post_date:
                        # For initial run, get all posts. For incremental, only new ones
                        if is_initial_run or post_date > last_timestamp:
                            posts.append({
                                'post_id': post_id,
                                'author': author,
                                'timestamp_utc': post_date.isoformat(),
                                'content': content[:9500],  # Limit content length
                            })
                            posts_on_page += 1
                    
                except Exception as e:
                    print(f"        ⚠️  Error processing post: {e}")
                    continue
            
            if posts_on_page > 0:
                print(f"        ✅ Added {posts_on_page} posts from this page")
            
            # Look for next page
            current_url = None
            
            # Method 1: Look for "Next" arrow
            next_li = soup.find('li', class_='arrow next')
            if next_li and next_li.a and 'href' in next_li.a.attrs:
                href = next_li.a['href']
                current_url = urljoin(thread_url, href)
            else:
                # Method 2: Look for pagination
                pagination = soup.find('div', class_='pagination') or soup.find('ul', class_='pagination')
                if pagination:
                    next_link = pagination.find('a', text=re.compile(r'Następ|Next|»'))
                    if next_link and 'href' in next_link.attrs:
                        href = next_link['href']
                        current_url = urljoin(thread_url, href)
            
            if current_url:
                time.sleep(0.5)  # Small delay between pages
        
        except Exception as e:
            print(f"      💥 Error scraping thread page {page_num}: {e}")
            break
    
    return posts

def main():
    """Main function with support for full and incremental scraping."""
    print("🚀 Starting Forum Scraper v5 (Enhanced)")
    print("=" * 50)
    
    # Check for command line arguments
    force_full_scrape = '--full' in sys.argv or '-f' in sys.argv
    
    # Check credentials
    if not FORUM_USERNAME or not FORUM_PASSWORD:
        print("❌ ERROR: Missing credentials!")
        print("   Please create a .env file with:")
        print("   FORUM_USERNAME=your_username")
        print("   FORUM_PASSWORD=your_password")
        return
    
    print(f"👤 Username: {FORUM_USERNAME}")
    print(f"🔑 Password: {'*' * len(FORUM_PASSWORD)}")
    
    config = load_config()
    last_timestamp, is_initial_run = load_state()
    
    # Check if forcing full scrape
    if force_full_scrape:
        print("🔄 FORCED FULL SCRAPE MODE")
        is_initial_run = True
        last_timestamp = datetime(2000, 1, 1, tzinfo=timezone.utc)
    elif is_initial_run:
        print("📌 INITIAL FULL SCRAPE MODE")
    else:
        print("📌 INCREMENTAL UPDATE MODE")
    
    if is_initial_run:
        print(f"📅 Getting ALL posts from the forum")
    else:
        print(f"📅 Looking for posts newer than: {last_timestamp.strftime('%Y-%m-%d %H:%M UTC')}")
    
    print("=" * 50)
    
    session = create_session()
    
    # Try login with retries
    max_retries = 2
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"\n🔄 Retry attempt {attempt + 1}/{max_retries}")
            time.sleep(5)
        
        if login_to_forum(session):
            break
    else:
        print("\n💥 Login failed after all attempts")
        return
    
    print("=" * 50)
    
    # Get all threads
    threads = get_gpw_threads(session)
    
    if not threads:
        print("💥 No threads found")
        return
    
    print(f"\n🔄 Processing {len(threads)} threads...")
    print("=" * 50)
    
    all_new_data = {}
    newest_timestamp = last_timestamp
    total_new_posts = 0
    
    for i, thread in enumerate(threads[:6], 1):
        print(f"\n[{i}/{len(threads)}] 📖 Thread: {thread['title'][:60]}...")
        print(f"    🔗 URL: {thread['url']}")
        
        try:
            posts = scrape_thread(session, thread['url'], thread['id'], last_timestamp, is_initial_run)
            
            if posts:
                all_new_data[thread['id']] = {
                    'thread_id': thread['id'],
                    'thread_title': thread['title'],
                    'thread_url': thread['url'],
                    'initial_post_author': posts[0]['author'] if posts else 'Unknown',
                    'posts': posts
                }
                
                total_new_posts += len(posts)
                print(f"    ✅ Found {len(posts)} new posts")
                
                # Update newest timestamp
                for post in posts:
                    post_time = datetime.fromisoformat(post['timestamp_utc'])
                    if post_time > newest_timestamp:
                        newest_timestamp = post_time
            else:
                print(f"    ℹ️  No new posts in this thread")
            
            # Delay between threads
            delay = config.get('delay_between_requests_sec', 2)
            if i < len(threads):  # Don't delay after last thread
                time.sleep(delay)
                
        except Exception as e:
            print(f"    💥 Error processing thread: {e}")
            continue
        
        # Progress indicator every 10 threads
        if i % 10 == 0:
            print(f"\n📊 Progress: {i}/{len(threads)} threads processed, {total_new_posts} new posts found so far")
    
    print("=" * 50)
    
    # Save results
    if all_new_data:
        print(f"\n🎉 SUCCESS! Found {total_new_posts} new posts in {len(all_new_data)} threads")
        update_output_file(all_new_data)
        
        # After initial scrape, switch to incremental mode
        if is_initial_run:
            print("📌 Initial scrape complete. Future runs will be incremental.")
            save_state(newest_timestamp, is_initial=False)
        else:
            save_state(newest_timestamp, is_initial=False)
    else:
        print("\n📝 No new posts found")
        if is_initial_run:
            # Even if no posts, mark initial scrape as done
            save_state(newest_timestamp, is_initial=False)
        else:
            save_state(newest_timestamp, is_initial=False)
    
    print("\n✅ Scraping completed successfully!")
    print("=" * 50)
    
    # Summary statistics
    if all_new_data:
        print("\n📊 Summary Statistics:")
        print(f"   • Total threads processed: {len(threads)}")
        print(f"   • Threads with new posts: {len(all_new_data)}")
        print(f"   • Total new posts: {total_new_posts}")
        print(f"   • Latest post timestamp: {newest_timestamp.strftime('%Y-%m-%d %H:%M UTC')}")

if __name__ == "__main__":
    main()