"""Unit tests for GitHub HMAC signature verification, branch key parser, and Figma URL parser."""

from src.services.figma_service import parse_figma_url
from src.services.github_service import extract_task_keys_from_text, verify_github_signature


def test_extract_task_keys():
    text = "feat: add oauth2 login closes A3Z-101 and refs ENG-42 in feature/A3Z-101-auth"
    keys = extract_task_keys_from_text(text)
    assert keys == ["A3Z-101", "ENG-42"]

    empty_keys = extract_task_keys_from_text("Just normal commit message")
    assert empty_keys == []


def test_github_hmac_signature():
    secret = "secret-token-123"
    body = b'{"action": "opened"}'
    import hashlib
    import hmac

    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_github_signature(body, secret, sig) is True
    assert verify_github_signature(body, secret, "sha256=invalidhash") is False
    assert verify_github_signature(body, secret, None) is False


def test_figma_url_parser():
    url_with_node = "https://www.figma.com/file/aBc123XYZ/App-Design?node-id=10%3A20"
    file_key, node_id = parse_figma_url(url_with_node)
    assert file_key == "aBc123XYZ"
    assert node_id == "10:20"

    url_design = "https://figma.com/design/99XYZ/Dashboard?node-id=4-5"
    file_key2, node_id2 = parse_figma_url(url_design)
    assert file_key2 == "99XYZ"
    assert node_id2 == "4:5"
