"""
ClipForge AI — CLI Test: Download Worker

Test the download worker directly (without Celery) to verify:
1. YouTube URL download via yt-dlp
2. Local folder/file ingestion
3. Output file creation

Usage:
    # Test YouTube download
    uv run python -m tests.test_download --youtube "https://www.youtube.com/watch?v=VIDEO_ID"

    # Test local file ingestion
    uv run python -m tests.test_download --local "D:/path/to/video.mp4"

    # Test local folder ingestion
    uv run python -m tests.test_download --local "D:/path/to/folder/"
"""
import argparse
import sys
import uuid
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.workers.download import (
    _download_youtube,
    _get_project_dir,
    _ingest_local_folder,
)


def test_youtube(url: str) -> None:
    """Test YouTube download."""
    project_id = str(uuid.uuid4())
    project_dir = _get_project_dir(project_id)
    output_path = project_dir / "source.mp4"

    print(f"Project ID: {project_id}")
    print(f"Output dir: {project_dir}")
    print(f"Downloading: {url}")
    print("-" * 60)

    try:
        metadata = _download_youtube(url, output_path)
        print(f"Title:      {metadata.get('title')}")
        print(f"Duration:   {metadata.get('duration_sec')}s")
        print(f"Resolution: {metadata.get('resolution')}")
        print(f"Uploader:   {metadata.get('uploader')}")

        # Check output
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"\n[OK] Downloaded: {output_path} ({size_mb:.2f} MB)")
        else:
            # Check for other extensions
            files = list(project_dir.glob("source.*"))
            if files:
                actual = files[0]
                size_mb = actual.stat().st_size / (1024 * 1024)
                print(f"\n[OK] Downloaded: {actual} ({size_mb:.2f} MB)")
            else:
                print(f"\n[FAIL] No output file found in {project_dir}")

    except ValueError as e:
        print(f"\n[FAIL] {e}")
    except Exception as e:
        print(f"\n[ERROR] Unexpected: {e}")
        raise


def test_local(path: str) -> None:
    """Test local folder/file ingestion."""
    project_id = str(uuid.uuid4())
    project_dir = _get_project_dir(project_id)

    print(f"Project ID: {project_id}")
    print(f"Output dir: {project_dir}")
    print(f"Source:     {path}")
    print("-" * 60)

    try:
        metadata = _ingest_local_folder(path, project_dir)
        print(f"Title:     {metadata.get('title')}")
        print(f"Size:      {metadata.get('file_size_mb')} MB")
        print(f"Files:     {metadata.get('file_count')}")

        output_path = project_dir / "source.mp4"
        if output_path.exists():
            print(f"\n[OK] Ingested: {output_path}")
        else:
            print(f"\n[FAIL] No source.mp4 in {project_dir}")

    except ValueError as e:
        print(f"\n[FAIL] {e}")
    except Exception as e:
        print(f"\n[ERROR] Unexpected: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Test ClipForge download worker")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--youtube", "-y", help="YouTube URL to download")
    group.add_argument("--local", "-l", help="Local file or folder path to ingest")

    args = parser.parse_args()

    print("=" * 60)
    print("ClipForge AI — Download Worker Test")
    print(f"Media dir: {settings.MEDIA_DIR}")
    print("=" * 60)

    if args.youtube:
        test_youtube(args.youtube)
    elif args.local:
        test_local(args.local)

    print("=" * 60)


if __name__ == "__main__":
    main()
