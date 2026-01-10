import os
import aiofiles

def pre_allocate_file(filename: str, size: int):
    """
    Creates an empty file of the specified size.
    """
    with open(filename, 'wb') as f:
        f.truncate(size)

def write_segment_sync(filename: str, offset: int, data: bytes):
    """
    Writes data to the file at a specific offset synchronously.
    Thread-safe enough for our use case if called carefully or via executor,
    but the OS file module in Python handles concurrent writes to different regions of the same file 
    mostly okay on modern OSs, though usually we want to avoid race conditions. 
    However, info.md suggests: "Synchronous function run via an executor or called after gather".
    """
    with open(filename, 'r+b') as f:
        f.seek(offset)
        f.write(data)

async def write_segment_async(filename: str, offset: int, data: bytes):
    """
    Writes data using aiofiles (which runs in a thread pool executor usually).
    """
    async with aiofiles.open(filename, 'r+b') as f:
        await f.seek(offset)
        await f.write(data)
