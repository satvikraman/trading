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
ENV_ICICI_VALID_UNTIL_KEY = "icici_dataset_valid_until_date"
ENV_PAYTM_VALID_UNTIL_KEY = "paytm_dataset_valid_until_date"
DEFAULT_PAYTM_NSE_URL = (
    "https://developer.paytmmoney.com/data/v1/scrips/nse_security_master.csv"
)
DEFAULT_PAYTM_BSE_URL = (
    "https://developer.paytmmoney.com/data/v1/scrips/bse_security_master.csv"
)
# Backward-compatible alias
ENV_VALID_UNTIL_KEY = ENV_ICICI_VALID_UNTIL_KEY


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
    valid_until = os.environ.get(ENV_ICICI_VALID_UNTIL_KEY, "")
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
                dotenv.set_key(str(env_file), ENV_ICICI_VALID_UNTIL_KEY, today)
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


def ensure_paytm_security_master(
    repo_root: Path | str,
    *,
    nse_url: str = DEFAULT_PAYTM_NSE_URL,
    bse_url: str = DEFAULT_PAYTM_BSE_URL,
    nse_dataset: str = "./dataset/nse_security_master.csv",
    bse_dataset: str = "./dataset/bse_security_master.csv",
    env_path: Path | str = "./.env",
    logger: logging.Logger | None = None,
    force: bool = False,
) -> tuple[dict[str, Path], bool]:
    """
    Download Paytm NSE/BSE security master CSVs once per calendar day.
    Used for daily circuit (upper/lower) limits before placing limit orders.
    """
    log = logger or logging.getLogger(__name__)
    root = Path(repo_root).resolve()
    paths = {
        "NSE": resolve_repo_path(root, nse_dataset),
        "BSE": resolve_repo_path(root, bse_dataset),
    }

    env_file = Path(env_path)
    if not env_file.is_absolute():
        env_file = (root / env_file).resolve()
    if env_file.is_file():
        dotenv.load_dotenv(env_file, override=False)

    today = datetime.datetime.today().strftime("%d-%b-%Y")
    valid_until = os.environ.get(ENV_PAYTM_VALID_UNTIL_KEY, "")
    nse_file = paths["NSE"]
    bse_file = paths["BSE"]

    need_download = (
        force
        or valid_until.upper() != today.upper()
        or not nse_file.is_file()
        or not bse_file.is_file()
    )
    downloaded = False
    if need_download:
        paths["NSE"].parent.mkdir(parents=True, exist_ok=True)
        for exchange, url, dest in (
            ("NSE", nse_url, paths["NSE"]),
            ("BSE", bse_url, paths["BSE"]),
        ):
            try:
                log.info("Downloading Paytm %s security master from %s", exchange, url)
                urllib.request.urlretrieve(url, dest)
                downloaded = True
            except Exception as exc:
                log.warning("Paytm %s security master download failed: %s", exchange, exc)
        if downloaded and env_file.parent.exists():
            dotenv.set_key(str(env_file), ENV_PAYTM_VALID_UNTIL_KEY, today)
        if not nse_file.is_file():
            log.warning(
                "nse_security_master.csv missing after download; "
                "circuit limit checks will allow orders with warnings"
            )

    return paths, downloaded
