#!/usr/bin/env python3
"""
Debug script to analyze Vimeo embeds on a page
"""

import requests
import re
import os
from pathlib import Path

def debug_vimeo_page():
    """Fetch page and analyze Vimeo embed patterns"""
    test_url = "https://mvsm.com/project/paper-pro-move"
    
    print(f"Fetching: {test_url}")
    
    # Fetch the page
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }
    
    try:
        response = requests.get(test_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        html_content = response.text
        print(f"✓ Successfully fetched page: {len(html_content)} characters")
        print(f"Response encoding: {response.encoding}")
        print(f"Response content-type: {response.headers.get('content-type', 'Unknown')}")
        print()
        
        # Save full HTML to file
        output_file = Path(__file__).parent / "mvsm_page.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✓ HTML saved to: {output_file}")
        print()
        
        # Search for specific patterns
        search_terms = ["vimeo", "player", "iframe", "video", "embed", "data-src"]
        
        for term in search_terms:
            print(f"=== Searching for '{term}' ===")
            
            # Case-insensitive search with context
            pattern = f".*{re.escape(term)}.*"
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            
            if matches:
                print(f"Found {len(matches)} matches:")
                for i, match in enumerate(matches[:10]):  # Show first 10 matches
                    # Clean up whitespace for display
                    clean_match = ' '.join(match.split())
                    if len(clean_match) > 200:
                        clean_match = clean_match[:200] + "..."
                    print(f"  {i+1}: {clean_match}")
                if len(matches) > 10:
                    print(f"  ... and {len(matches) - 10} more matches")
            else:
                print("No matches found")
            print()
        
        # Look specifically for potential Vimeo IDs (6-12 digit numbers)
        print("=== Potential Vimeo IDs (6-12 digits) ===")
        vimeo_id_pattern = r'\b(\d{6,12})\b'
        potential_ids = re.findall(vimeo_id_pattern, html_content)
        
        if potential_ids:
            # Remove duplicates and sort
            unique_ids = sorted(list(set(potential_ids)))
            print(f"Found {len(unique_ids)} unique potential IDs:")
            for id_num in unique_ids:
                print(f"  {id_num}")
        else:
            print("No potential Vimeo IDs found")
        print()
        
        # Look for specific Vimeo-related patterns
        print("=== Vimeo-specific patterns ===")
        vimeo_patterns = [
            (r'player\.vimeo\.com/video/(\d+)', "Standard Vimeo player embed"),
            (r'vimeo\.com/(?:video/)?(\d+)', "Direct Vimeo link"),
            (r'"video_id"\s*:\s*"?(\d+)"?', "video_id in JSON"),
            (r'data-vimeo-id["\']?\s*=\s*["\']?(\d+)["\']?', "data-vimeo-id attribute"),
            (r'src["\']?\s*=\s*["\'][^"\']*vimeo[^"\']*["\']', "src attribute with vimeo"),
        ]
        
        found_any = False
        for pattern, description in vimeo_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                found_any = True
                print(f"{description}: {matches}")
        
        if not found_any:
            print("No specific Vimeo patterns found")
        print()
        
        # Sample of the HTML for manual inspection
        print("=== HTML Sample (first 1000 characters) ===")
        print(html_content[:1000])
        print("...")
        print()
        
        print("=== HTML Sample (middle section) ===")
        middle_start = len(html_content) // 2
        print(html_content[middle_start:middle_start + 1000])
        print("...")
        
    except requests.RequestException as e:
        print(f"✗ Error fetching page: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

if __name__ == "__main__":
    debug_vimeo_page()