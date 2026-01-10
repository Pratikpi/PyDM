import asyncio
import os
import aiohttp
from typing import Optional, Callable
from .models import DownloadState, Segment, SegmentStatus
from ..utils.file_ops import pre_allocate_file, write_segment_async
import logging

logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self, url: str, output_file: str, num_segments: int = 8, max_concurrent: int = 4):
        self.url = url
        self.output_file = output_file
        self.num_segments = num_segments
        self.max_concurrent = max_concurrent
        output_dir = os.path.dirname(output_file) or '.'
        output_name = os.path.basename(output_file)
        self.state_file = os.path.join(output_dir, f".{output_name}.state")
        self.state: Optional[DownloadState] = None
        # Callback signature: (segment_id, bytes_written)
        self._progress_callback: Optional[Callable[[int, int], None]] = None

    def set_progress_callback(self, callback: Callable[[int, int], None]):
        self._progress_callback = callback

    async def start(self):
        # 1. Load or Initialize State
        if os.path.exists(self.state_file):
            logger.info("Found existing state file. Resuming...")
            self._load_state()
        else:
            logger.info("Starting new download...")
            await self._initialize_new_download()

        if not self.state:
            raise RuntimeError("Failed to initialize download state.")

        # 2. Prepare File
        if not os.path.exists(self.output_file):
             # If resuming but output file missing, we arguably should restart or warn.
             # For simplicity, we assume if state exists, file exists or we recreate it (but segments might be lost).
             # If completely lost, resetting state is safer.
             if any(s.status == SegmentStatus.COMPLETED for s in self.state.segments):
                 logger.warning("Output file missing but state says completed segments exist. Resetting state.")
                 await self._initialize_new_download() # Re-init
             else:
                 pre_allocate_file(self.output_file, self.state.total_size)
        
        # Ensure file size is correct
        current_size = os.path.getsize(self.output_file)
        if current_size != self.state.total_size:
             # Basic check.
             logger.info(f"File size mismatch ({current_size} != {self.state.total_size}). Adjusting...")
             pre_allocate_file(self.output_file, self.state.total_size) # This truncates/expands

        # 3. Download Loop
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        pending_segments = [s for s in self.state.segments if s.status != SegmentStatus.COMPLETED]
        if not pending_segments:
            logger.info("Download already complete.")
            return

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._download_segment(session, segment, semaphore)
                for segment in pending_segments
            ]
            await asyncio.gather(*tasks)

        # 4. Cleanup
        if all(s.status == SegmentStatus.COMPLETED for s in self.state.segments):
            logger.info("Download completed successfully.")
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
        else:
            logger.warning("Download finished but not all segments completed.")

    async def _initialize_new_download(self):
        async with aiohttp.ClientSession() as session:
            async with session.head(self.url) as response:
                if response.status >= 400:
                    raise RuntimeError(f"Failed to fetch metadata: {response.status}")
                
                total_size = int(response.headers.get('Content-Length', 0))
                accept_ranges = response.headers.get('Accept-Ranges', 'none')
                range_supported = 'bytes' in accept_ranges or accept_ranges == 'bytes'

                if not range_supported:
                    logger.warning("Server does not support ranges. Fallback to single segment.")
                    self.num_segments = 1

                if total_size == 0:
                    # Some servers don't send Content-Length for chunked transfer
                    # In that case, multi-threaded download is hard/impossible without known size
                    raise RuntimeError("Cannot determine file size (Content-Length missing).")

                segments = self._calculate_segments(total_size, self.num_segments)
                self.state = DownloadState(
                    url=self.url,
                    output_file=self.output_file,
                    total_size=total_size,
                    segments=segments
                )
                
                pre_allocate_file(self.output_file, total_size)
                self._save_state()

    def _calculate_segments(self, total_size: int, num_segments: int) -> list[Segment]:
        segments = []
        segment_size = total_size // num_segments
        for i in range(num_segments):
            start = i * segment_size
            # Last segment gets the remainder
            end = (start + segment_size - 1) if i < num_segments - 1 else total_size - 1
            segments.append(Segment(id=i, start=start, end=end, status=SegmentStatus.PENDING))
        return segments

    async def _download_segment(self, session: aiohttp.ClientSession, segment: Segment, semaphore: asyncio.Semaphore):
        async with semaphore:
            # Check if partially downloaded? 
            # Logic: If failed/pending, we start from start + downloaded_bytes 
            # But the requirement says "write it directly to the file... offset...".
            # If we resume, we should seek to correct place.
            
            # Simple resume: If status is FAILED/PENDING, we reset downloaded_bytes to 0 implicitly unless we trust it.
            #info.md says: "Resume Logic... Only ... for segments PENDING or FAILED"
            # It also says: "Update state... only when a segment is fully completed".
            # This implies we DON'T keep partial segment progress in the state file for safety,
            # OR we do, but we need to verify.
            # "downloaded_bytes: For partially failed segments, track how much was saved."
            # If we trust `downloaded_bytes`, we could resume mid-segment.
            # Header: Range: bytes={current_start}-{end}
            
            current_start = segment.start + segment.downloaded_bytes
            if current_start > segment.end:
                segment.status = SegmentStatus.COMPLETED
                self._save_state()
                return

            headers = {'Range': f'bytes={current_start}-{segment.end}'}
            logger.debug(f"Starting segment {segment.id}: {headers}")
            
            segment.status = SegmentStatus.IN_PROGRESS
            # (Don't save state on IN_PROGRESS to reduce IO? Or do? info.md says update on completion)
            
            try:
                async with session.get(self.url, headers=headers) as response:
                    response.raise_for_status()
                    
                    async for chunk in response.content.iter_chunked(8192):
                        # Write chunk
                        write_offset = segment.start + segment.downloaded_bytes
                        await write_segment_async(self.output_file, write_offset, chunk)
                        
                        chunk_len = len(chunk)
                        segment.downloaded_bytes += chunk_len
                        
                        if self._progress_callback:
                            self._progress_callback(segment.id, chunk_len)
                            
                    # Finished segment
                    segment.status = SegmentStatus.COMPLETED
                    self._save_state()
                    logger.debug(f"Segment {segment.id} complete.")

            except Exception as e:
                logger.error(f"Error downloading segment {segment.id}: {e}")
                segment.status = SegmentStatus.FAILED
                self._save_state()
                # We do not re-raise to allow other segments to continue? 
                # Or we let gather handle exceptions? 
                # Usually better to suppress and retry later or let the whole thing fail gracefully?
                # For now, just mark FAILED.

    def _save_state(self):
        with open(self.state_file, 'w') as f:
            f.write(self.state.to_json())

    def _load_state(self):
        with open(self.state_file, 'r') as f:
            json_str = f.read()
            self.state = DownloadState.from_json(json_str)

