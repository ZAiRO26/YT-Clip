"""
ClipForge AI — Kokoro TTS Model Download & Verification Script

Provenance & Model Card:
- Upstream Model: Kokoro v0.19 (Apache-2.0, by hexgrad / StyleTTS2 + ISTFTNet architecture)
- Port & ONNX Export: kokoro-onnx by thewh1teagle (https://github.com/thewh1teagle/kokoro-onnx)
- Release Tag / Source URLs:
  * https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx
  * https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin
- Official Model Card: https://huggingface.co/hexgrad/Kokoro-82M
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "kokoro"

ASSETS = [
    {
        "filename": "kokoro-v0_19.onnx",
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
        "sha256": "dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c",
        "expected_size_mb": 310.4,
    },
    {
        "filename": "voices.bin",
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin",
        "sha256": "157eab2fa1dd1c91b46599ea6f514bf86f66944c0c760250ed324e6cd99af075",
        "expected_size_mb": 5.5,
    },
]


def verify_sha256(file_path: Path, expected_hash: str) -> bool:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest() == expected_hash


def ensure_kokoro_models() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Checking Kokoro ONNX model assets in {MODELS_DIR}...")

    for asset in ASSETS:
        target = MODELS_DIR / asset["filename"]
        if target.exists():
            print(f"  [Verify] {asset['filename']} exists ({target.stat().st_size / (1024*1024):.1f} MB). Verifying SHA-256...")
            if verify_sha256(target, asset["sha256"]):
                print(f"  [PASS] SHA-256 verified for {asset['filename']}")
                continue
            else:
                print(f"  [WARN] Checksum mismatch for {asset['filename']}. Re-downloading...")
                target.unlink(missing_ok=True)

        print(f"  [Download] Fetching {asset['filename']} from {asset['url']}...")
        try:
            urllib.request.urlretrieve(asset["url"], target)
        except Exception as e:
            raise RuntimeError(f"Failed to download {asset['filename']} from {asset['url']}: {e}")

        if not verify_sha256(target, asset["sha256"]):
            target.unlink(missing_ok=True)
            raise RuntimeError(f"SHA-256 verification failed after downloading {asset['filename']}!")

        print(f"  [PASS] Successfully downloaded and verified {asset['filename']}")

    print("[SUCCESS] Kokoro ONNX models ready for offline inference.")


if __name__ == "__main__":
    ensure_kokoro_models()
