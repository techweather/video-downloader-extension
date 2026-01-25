"""
Test URL configurations organized by platform type
"""

# Test URLs for different platforms and media types
# NOTE: These are example URLs for testing purposes. 
# Replace with actual test URLs as needed for integration tests.

TEST_URLS = {
    'youtube': {
        'video': [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # Rick Roll (famous test video)
            'https://youtu.be/dQw4w9WgXcQ',  # Short URL format
            'https://www.youtube.com/watch?v=jNQXAC9IVRw'  # Another test video
        ],
        'playlist': [
            'https://www.youtube.com/playlist?list=PLrAXtmRdnEQy8VG4zCVAOo_m5rqxnhGf1'
        ],
        'shorts': [
            'https://www.youtube.com/shorts/abc123'
        ]
    },
    
    'instagram': {
        'post': [
            'https://www.instagram.com/p/ABC123/',
            'https://instagram.com/p/DEF456/'
        ],
        'story': [
            'https://www.instagram.com/stories/username/1234567890'
        ],
        'reel': [
            'https://www.instagram.com/reel/GHI789/',
            'https://instagram.com/reels/video/JKL012/'
        ],
        'carousel': [
            'https://www.instagram.com/p/MNO345/',  # Multi-image/video post
        ]
    },
    
    'vimeo': {
        'video': [
            'https://vimeo.com/1234567',
            'https://player.vimeo.com/video/7654321'
        ],
        'private': [
            'https://vimeo.com/1111111/abcdef123456'  # Private video with unlock code
        ]
    },
    
    'tiktok': {
        'video': [
            'https://www.tiktok.com/@username/video/1234567890',
            'https://tiktok.com/@user/video/0987654321'
        ]
    },
    
    'direct_video': {
        'mp4': [
            'https://example.com/video.mp4',
            'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4'
        ],
        'webm': [
            'https://example.com/video.webm'
        ],
        'mov': [
            'https://example.com/video.mov'
        ]
    },
    
    'image_pages': {
        'imgur': [
            'https://imgur.com/a/ABC123',
            'https://i.imgur.com/DEF456.jpg'
        ],
        'reddit': [
            'https://www.reddit.com/r/pics/comments/abc123/title/',
            'https://i.redd.it/abc123.jpg'
        ],
        'generic': [
            'https://example.com/page-with-image.html'
        ]
    },
    
    'direct_images': {
        'jpg': [
            'https://example.com/image.jpg',
            'https://picsum.photos/800/600.jpg'  # Lorem Picsum test image
        ],
        'png': [
            'https://example.com/image.png',
            'https://via.placeholder.com/600x400.png'  # Placeholder image
        ],
        'gif': [
            'https://example.com/animated.gif'
        ],
        'webp': [
            'https://example.com/image.webp'
        ]
    }
}

# Invalid URLs for testing error handling
INVALID_URLS = {
    'malformed': [
        'not-a-url',
        'http://',
        'https://',
        'ftp://example.com/file.mp4',  # Unsupported protocol
        '//example.com/video.mp4'  # Missing protocol
    ],
    
    'non_existent': [
        'https://youtube.com/watch?v=NONEXISTENT123',
        'https://instagram.com/p/FAKE123/',
        'https://example.com/404-video.mp4'
    ],
    
    'private_or_restricted': [
        'https://youtube.com/watch?v=PRIVATE123',
        'https://instagram.com/p/PRIVATE456/',
        'https://vimeo.com/PRIVATE789'
    ]
}

# Platform-specific test scenarios
TEST_SCENARIOS = {
    'youtube': {
        'age_restricted': [
            # URLs that might have age restrictions
            'https://youtube.com/watch?v=AGE_RESTRICTED'
        ],
        'live_stream': [
            # Live stream URLs (may not be downloadable)
            'https://youtube.com/watch?v=LIVE_STREAM'
        ]
    },
    
    'instagram': {
        'private_account': [
            # Posts from private accounts
            'https://instagram.com/p/PRIVATE_ACCOUNT/'
        ],
        'expired_story': [
            # Story that has expired (24h limit)
            'https://instagram.com/stories/user/EXPIRED'
        ]
    }
}

# Quality/format testing
QUALITY_TEST_URLS = {
    '4k': [
        'https://youtube.com/watch?v=4K_VIDEO'
    ],
    'hd': [
        'https://youtube.com/watch?v=HD_VIDEO'
    ],
    'audio_only': [
        'https://youtube.com/watch?v=MUSIC_VIDEO'
    ]
}

# Helper functions for test URL management
def get_test_urls(platform=None, media_type=None):
    """
    Get test URLs filtered by platform and/or media type
    
    Args:
        platform (str): Platform name (youtube, instagram, etc.)
        media_type (str): Media type (video, image, etc.)
    
    Returns:
        list: Filtered list of test URLs
    """
    if platform and media_type:
        return TEST_URLS.get(platform, {}).get(media_type, [])
    elif platform:
        urls = []
        for media_types in TEST_URLS.get(platform, {}).values():
            urls.extend(media_types)
        return urls
    else:
        all_urls = []
        for platform_data in TEST_URLS.values():
            for media_type_urls in platform_data.values():
                all_urls.extend(media_type_urls)
        return all_urls

def get_sample_url(platform, media_type=None):
    """
    Get a single sample URL for testing
    
    Args:
        platform (str): Platform name
        media_type (str): Optional media type
    
    Returns:
        str: Sample URL or None if not found
    """
    urls = get_test_urls(platform, media_type)
    return urls[0] if urls else None

def is_platform_url(url, platform):
    """
    Check if a URL belongs to a specific platform
    
    Args:
        url (str): URL to check
        platform (str): Platform name
    
    Returns:
        bool: True if URL belongs to platform
    """
    platform_domains = {
        'youtube': ['youtube.com', 'youtu.be'],
        'instagram': ['instagram.com'],
        'vimeo': ['vimeo.com'],
        'tiktok': ['tiktok.com']
    }
    
    domains = platform_domains.get(platform, [])
    return any(domain in url for domain in domains)

# Configuration for test runs
TEST_CONFIG = {
    'timeout_seconds': 30,
    'max_retries': 3,
    'download_dir': '/tmp/media_downloader_tests',
    'enable_cleanup': True,
    'mock_downloads': True  # Set to False for actual download testing
}