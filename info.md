# 🐍 PyDM: Python Asynchronous Download Manager Project Guide

This document serves as a reference for building a high-performance, segmented download manager (PyDM) using Python's `asyncio` framework.

---

## 🎯 Project Goals

1.  **High-Speed Download:** Achieve faster speeds by utilizing **concurrent, segmented downloading**.
2.  **Reliability:** Implement **download resume capability** to handle interruptions gracefully.
3.  **Efficiency:** Use **`asyncio`** to manage multiple network I/O tasks efficiently within a single thread.

---

## 🛠️ Technology Stack

| Component | Purpose | Library/Module |
| :--- | :--- | :--- |
| **Concurrency Core** | Manages the asynchronous event loop and concurrent tasks. | `asyncio` (Built-in) |
| **HTTP Requests** | Performs non-blocking network requests (GET, HEAD). | `aiohttp`, `httpx` |
| **State Management** | Stores download progress for resumption. | `json` (Built-in) |
| **User Interface** | Provides visual feedback on download progress. | `tqdm` (Optional for CLI) |
| **File Handling** | Low-level file creation and writing at specific offsets. | `os`, `io` (Built-in) |

---

## 🏗️ Architecture Overview

The PyDM architecture is based on the principle of **Divide and Conquer** applied to network I/O. 

1.  **Header Check:** Verify server capability (`Accept-Ranges: bytes`).
2.  **Segmentation:** Divide the total file size into $N$ byte ranges.
3.  **Task Creation:** Create $N$ independent `async` tasks, each requesting a specific byte range using the HTTP `Range` header.
4.  **Concurrent Execution:** The `asyncio` event loop schedules and executes these tasks concurrently.
5.  **Reconstruction (Merge):** As each segment completes, its data is written to the correct byte offset in the final output file.

---

## 📝 Milestone 1: Initialization & Segmentation

### 1. Initial Head Request
The first step is to gather metadata about the file.

* **Action:** Send an **`aiohttp` HEAD request** to the file URL.
* **Data Extraction:**
    * **Total Size:** Read the `Content-Length` header.
    * **Range Support:** Check for `Accept-Ranges: bytes`.
* **Code Snippet Focus:**

    ```python
    async with aiohttp.ClientSession() as session:
        async with session.head(url) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            range_supported = 'bytes' in response.headers.get('Accept-Ranges', '')
            # ...
    ```

### 2. Segment Calculation
Divide the total size into manageable byte ranges (e.g., $N=8$).

* **Input:** `total_size` (bytes), `segment_count` ($N$).
* **Output:** A list of `(start_byte, end_byte)` tuples.
* **Logic:**
    * `segment_size = total_size // N`
    * The last segment must account for any remainder to ensure the full file is downloaded.

---

## 🚀 Milestone 2: Concurrent Download & File Merging

### 3. Asynchronous Segment Downloader
Create the core worker function that handles a single download stream.

* **Function Signature:** `async def download_segment(url, start_byte, end_byte, output_filename):`
* **Action:**
    * Construct the **`Range` header**: `Range: bytes={start_byte}-{end_byte}`.
    * Initiate an **`aiohttp` GET request** with this header.
    * Read the stream and return the data, or write it directly to the file.

### 4. File Reconstruction (Writing)
Segments must be placed at their correct positions, regardless of the order they finish downloading.

* **Mechanism:** Use Python's built-in file handling capabilities.
* **Pre-Allocation:** Create the output file and potentially pre-allocate its space using `os.ftruncate()` if required for performance/robustness.
* **Atomic Writing:** Open the file in binary write mode (`'wb'`). Use `f.seek(offset)` before `f.write(data)` to move the file pointer to the correct position for each segment.

    ```python
    def write_segment(filename, offset, data):
        # Synchronous function run via an executor or called after gather
        with open(filename, 'rb+') as f: 
            f.seek(offset)
            f.write(data)
    ```

---

## 🛡️ Milestone 3: Download Resumption (State Management)

To resume, you must track the status of every segment.

### 5. State File (`.state` or `.json`)
This file persists the download metadata.

* **Contents:**
    1.  `url`: Original download URL.
    2.  `total_size`: Total file size.
    3.  `segments`: A list of dictionaries for each segment.
        * `id`: Segment identifier.
        * `start`: Original start byte.
        * `end`: Original end byte.
        * `status`: (`PENDING`, `COMPLETED`, `FAILED`).
        * `downloaded_bytes`: For partially failed segments, track how much was saved.

### 6. Resume Logic
When the downloader starts, check the state file:

* **If State Exists:**
    * Reload the segment list.
    * Only create and schedule `async` tasks for segments marked **`PENDING`** or **`FAILED`**.
* **Status Updates:**
    * Update the state file and persist it **only when a segment is fully completed and written to disk**. This ensures that if a crash occurs mid-segment, the next run can safely restart that segment.

---

## 💡 Advanced Considerations

* **Rate Limiting:** If the server limits simultaneous connections, you must use an `asyncio.Semaphore` to limit the number of active segment tasks running at any one time.
* **Error Handling:** Implement `try...except` blocks in the segment downloader to catch `aiohttp` exceptions (timeouts, connection reset). If an error occurs, update the segment status to `FAILED` and retry a set number of times.
* **Integrate `tqdm`:** Use `tqdm.asyncio.tqdm` or manually update a `tqdm` progress bar from within the asynchronous functions to provide a responsive and accurate progress display.
