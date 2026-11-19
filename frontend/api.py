"""Thin HTTP client for the CareerPilot API."""
import os

import requests
import streamlit as st


def api_url() -> str:
    url = os.getenv("API_URL")
    if not url:
        try:
            url = st.secrets["API_URL"]
        except Exception:  # no secrets file: running locally
            url = "http://127.0.0.1:8000"
    return str(url).rstrip("/")


class APIError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def _detail(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
    if isinstance(detail, list):  # FastAPI validation errors
        return "; ".join(
            f"{'.'.join(str(p) for p in d.get('loc', [])[1:])}: {d.get('msg', '')}" for d in detail
        )
    return str(detail)


def request(method: str, path: str, token: str | None = None, timeout: int = 90, **kwargs):
    """Returns parsed JSON (or None for 204). Raises APIError on any failure."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.request(method, api_url() + path, headers=headers, timeout=timeout, **kwargs)
    except requests.exceptions.RequestException:
        raise APIError(
            "Cannot reach the server. A free server sleeps when idle: wait about a minute and try again."
        )
    if response.status_code >= 400:
        raise APIError(_detail(response), response.status_code)
    return None if response.status_code == 204 else response.json()


def wake_server() -> bool:
    """A sleeping free server needs up to ~1 minute to answer the first request."""
    try:
        return requests.get(api_url() + "/health", timeout=90).ok
    except requests.exceptions.RequestException:
        return False