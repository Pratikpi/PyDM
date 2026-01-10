import argparse
import asyncio
import logging
import sys
from tqdm import tqdm
from ..core.downloader import Downloader

def main():
    parser = argparse.ArgumentParser(description="PyDM: Python Asynchronous Download Manager")
    parser.add_argument("url", help="URL of the file to download")
    parser.add_argument("-o", "--output", help="Output filename")
    parser.add_argument("-s", "--segments", type=int, default=8, help="Number of segments")
    parser.add_argument("-c", "--concurrency", type=int, default=4, help="Max concurrent connections")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING
    # Configure logging to write to stderr so it doesn't interfere easily (though tqdm handles stderr)
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    if not args.output:
        args.output = args.url.split('/')[-1]
        if not args.output:
            args.output = "downloaded_file"

    print(f"Downloading {args.url} to {args.output}")

    downloader = Downloader(
        url=args.url,
        output_file=args.output,
        num_segments=args.segments,
        max_concurrent=args.concurrency
    )

    # Bars container
    # total_bar: The main progress bar
    # segment_bars: Dict mapping segment_id -> tqdm bar
    bars = {
        'total': None,
        'segments': {}
    }

    def progress_callback(segment_id, bytes_written):
        # Initialize bars if not done
        if bars['total'] is None:
            if downloader.state:
                # 1. Main Global Bar
                # Calculate initial progress
                # Note: The 'bytes_written' passed here is just this chunk.
                # However, segment.downloaded_bytes in state *already includes* this chunk 
                # because we update it before callback in Downloader.
                # So to get the TRUE "start" for the bar we might need to be careful.
                # Actually, simpler: just sum up all downloaded_bytes from state.
                current_total_downloaded = sum(s.downloaded_bytes for s in downloader.state.segments)
                # But tqdm wants 'initial'. If we set initial=current, it starts there.
                # Then we update(bytes_written).
                # Wait, if we set initial=current, and then update(bytes_written), we double count?
                # No. 'initial' sets the starting point. subsequent updates add to it.
                # The very first callback comes AFTER the first chunk write.
                # So 'current_total_downloaded' includes 'bytes_written'.
                # So 'initial' should be 'current - bytes_written'.
                
                initial_total = current_total_downloaded - bytes_written
                
                bars['total'] = tqdm(
                    total=downloader.state.total_size,
                    initial=initial_total,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f"Total: {args.output}",
                    position=0,
                    leave=True
                )
                
                # 2. Segment Bars
                # We create one bar per segment.
                # Position starting from 1.
                sorted_segments = sorted(downloader.state.segments, key=lambda s: s.id)
                for i, seg in enumerate(sorted_segments):
                    # For segments, we know their capacity is (end - start + 1)
                    seg_size = seg.end - seg.start + 1
                    
                    # Initial for this segment?
                    # If this is the segment calling back, its downloaded_bytes includes the chunk.
                    seg_initial = seg.downloaded_bytes
                    if seg.id == segment_id:
                        seg_initial -= bytes_written
                        
                    bars['segments'][seg.id] = tqdm(
                        total=seg_size,
                        initial=seg_initial,
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=f"Seg {seg.id}",
                        position=i + 1,
                        leave=False, # Segments disappear or stay? IDM keeps them. Let's keep false to not clutter or True? 
                                     # Usually temporary bars should have leave=False, but then they might flicker.
                                     # Let's try leave=False but keep 'position' so they overwrite themselves in place.
                        bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}' # Compact format
                    )

        # Update Total
        if bars['total']:
            bars['total'].update(bytes_written)
        
        # Update Segment
        if bars['segments'].get(segment_id):
            bars['segments'][segment_id].update(bytes_written)

    downloader.set_progress_callback(progress_callback)

    try:
        asyncio.run(downloader.start())
    except KeyboardInterrupt:
        # Close bars to prevent terminal breakage
        if bars['total']: bars['total'].close()
        for b in bars['segments'].values(): b.close()
        print("\nDownload paused/cancelled.")
        sys.exit(0)
    except Exception as e:
        if bars['total']: bars['total'].close()
        for b in bars['segments'].values(): b.close()
        
        if args.verbose:
            logging.exception("An error occurred")
        else:
            print(f"Error: {e}")
        sys.exit(1)
    finally:
        if bars['total']: bars['total'].close()
        for b in bars['segments'].values(): b.close()

if __name__ == "__main__":
    main()
