"""Download and refresh ICICI Direct SecurityMaster (NSE/BSE/FNO scrip files)."""
from __future__ import annotations

import datetime
import logging
import os
import urllib.request
import zipfile
from pathlib import Path

import dotenv

DEFAULT_ICICI_ZIP_URL = (
    "https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip"
)
ENV_VALID_UNTIL_KEY = "icici_dataset_valid_until_date"


def resolve_repo_path(repo_root: Path, path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def ensure_icici_security_master(
    repo_root: Path | str,
    *,
    zip_url: str = DEFAULT_ICICI_ZIP_URL,
    nse_dataset: str = "./dataset/NSEScripMaster.txt",
    bse_dataset: str = "./dataset/BSEScripMaster.txt",
    fno_dataset: str = "./dataset/FONSEScripMaster.txt",
    env_path: Path | str = "./.env",
    logger: logging.Logger | None = None,
    force: bool = False,
) -> tuple[dict[str, Path], bool]:
    """
    Download ICICI SecurityMaster zip once per calendar day (same as appIcici / appIciciBreeze).
    Extracts NSEScripMaster.txt, BSEScripMaster.txt, FONSEScripMaster.txt into dataset/.
    """
    log = logger or logging.getLogger(__name__)
    root = Path(repo_root).resolve()
    paths = {
        "NSE": resolve_repo_path(root, nse_dataset),
        "BSE": resolve_repo_path(root, bse_dataset),
        "FNO": resolve_repo_path(root, fno_dataset),
    }
    dataset_dir = paths["NSE"].parent

    env_file = Path(env_path)
    if not env_file.is_absolute():
        env_file = (root / env_file).resolve()
    if env_file.is_file():
        dotenv.load_dotenv(env_file, override=True)

    today = datetime.datetime.today().strftime("%d-%b-%Y")
    valid_until = os.environ.get(ENV_VALID_UNTIL_KEY, "")
    nse_file = paths["NSE"]

    downloaded = False
    if force or valid_until.upper() != today.upper() or not nse_file.is_file():
        zip_path = dataset_dir / f"SecurityMaster-{today}.zip"
        try:
            log.info("Downloading ICICI SecurityMaster from %s", zip_url)
            urllib.request.urlretrieve(zip_url, zip_path)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(dataset_dir)
            if env_file.parent.exists():
                dotenv.set_key(str(env_file), ENV_VALID_UNTIL_KEY, today)
            log.info("SecurityMaster extracted to %s", dataset_dir)
            downloaded = True
        except Exception as exc:
            log.warning("SecurityMaster download failed: %s", exc)
            if not nse_file.is_file():
                raise RuntimeError(
                    "NSEScripMaster.txt is missing and download failed. "
                    "Check network or place files under dataset/ manually."
                ) from exc

    return paths, downloaded
