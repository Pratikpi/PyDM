import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pydm.core.downloader import Downloader
from pydm.core.models import SegmentStatus

@pytest.mark.asyncio
async def test_calculate_segments():
    downloader = Downloader("http://example.com", "test.file", num_segments=4)
    segments = downloader._calculate_segments(100, 4)
    
    assert len(segments) == 4
    assert segments[0].start == 0 and segments[0].end == 24
    assert segments[1].start == 25 and segments[1].end == 49
    assert segments[2].start == 50 and segments[2].end == 74
    assert segments[3].start == 75 and segments[3].end == 99

@pytest.mark.asyncio
async def test_calculate_segments_uneven():
    downloader = Downloader("http://example.com", "test.file", num_segments=3)
    segments = downloader._calculate_segments(100, 3)
    # 100 // 3 = 33
    # 0: 0-32
    # 1: 33-65
    # 2: 66-99
    assert len(segments) == 3
    assert segments[0].end - segments[0].start + 1 == 33
    assert segments[1].end - segments[1].start + 1 == 33
    assert segments[2].end - segments[2].start + 1 == 34 # Remainder

@pytest.mark.asyncio
async def test_init_new_download_mocks():
    # Mock aiohttp session
    with patch('aiohttp.ClientSession') as MockSession:
        session_instance = MockSession.return_value
        session_instance.__aenter__.return_value = session_instance
        
        # Mock HEAD response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {
            'Content-Length': '1000',
            'Accept-Ranges': 'bytes'
        }
        mock_response.__aenter__.return_value = mock_response
        
        session_instance.head.return_value = mock_response

        # Mock file ops
        with patch('pydm.core.downloader.pre_allocate_file') as mock_alloc, \
             patch('pydm.core.downloader.Downloader._save_state') as mock_save:
            
            downloader = Downloader("http://example.com/foo.zip", "foo.zip")
            await downloader._initialize_new_download()
            
            assert downloader.state is not None
            assert downloader.state.total_size == 1000
            assert len(downloader.state.segments) == 8 # default
            mock_alloc.assert_called_once_with("foo.zip", 1000)
            mock_save.assert_called()

