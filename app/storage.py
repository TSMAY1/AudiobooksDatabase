import os
from functools import lru_cache
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def storage_backend() -> str:
    backend = os.getenv("ASSET_STORAGE_BACKEND", "local").strip().lower()
    if backend not in {"local", "azure"}:
        raise ValueError("ASSET_STORAGE_BACKEND must be either 'local' or 'azure'.")
    return backend


def normalize_asset_path(stored_path: str) -> str:
    """Return a safe path relative to the project's assets directory."""
    if not stored_path:
        raise ValueError("No asset path was provided.")

    normalized = str(stored_path).replace("\\", "/").lstrip("/")
    parts = list(PurePosixPath(normalized).parts)

    if parts and parts[0].lower() == "assets":
        parts = parts[1:]

    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Invalid asset path: {stored_path!r}")

    return "/".join(parts)


def local_asset_path(stored_path: str) -> Path:
    relative_path = normalize_asset_path(stored_path)
    return PROJECT_ROOT / "assets" / Path(*relative_path.split("/"))


@lru_cache(maxsize=1)
def _container_client():
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise RuntimeError(
            "Azure storage packages are required when ASSET_STORAGE_BACKEND=azure."
        ) from exc

    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "").strip()
    container_name = os.getenv("AZURE_STORAGE_CONTAINER", "assets").strip()

    if not account_name:
        raise ValueError(
            "AZURE_STORAGE_ACCOUNT_NAME is required when ASSET_STORAGE_BACKEND=azure."
        )

    service = BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=DefaultAzureCredential(),
    )
    return service.get_container_client(container_name)


def read_asset_bytes(stored_path: str) -> bytes:
    if storage_backend() == "azure":
        blob_name = normalize_asset_path(stored_path)
        return _container_client().download_blob(blob_name).readall()

    path = local_asset_path(stored_path)
    if not path.exists():
        raise FileNotFoundError(f"Asset not found: {path}")
    return path.read_bytes()


def write_asset_bytes(stored_path: str, data: bytes) -> None:
    if storage_backend() == "azure":
        blob_name = normalize_asset_path(stored_path)
        _container_client().upload_blob(blob_name, data, overwrite=False)
        return

    path = local_asset_path(stored_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def delete_asset(stored_path: str) -> None:
    if storage_backend() == "azure":
        blob_name = normalize_asset_path(stored_path)
        _container_client().delete_blob(blob_name)
        return

    path = local_asset_path(stored_path)
    if path.exists():
        path.unlink()
