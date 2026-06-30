"""Project path helpers."""
import os
import sys

if getattr(sys, 'frozen', False):
    _BASE = os.path.join(os.path.dirname(sys.executable), '_internal')
    PROJECT_DIR = os.path.dirname(sys.executable)
    CORE_DIR = os.path.join(_BASE, 'core')
    TOOLS_DIR = os.path.join(_BASE, 'tools')
    WECHAT_DECRYPT_DIR = os.path.join(TOOLS_DIR, 'wechat-decrypt')
else:
    PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CORE_DIR = os.path.join(PROJECT_DIR, "core")
    TOOLS_DIR = os.path.join(PROJECT_DIR, "tools")
    WECHAT_DECRYPT_DIR = os.path.join(TOOLS_DIR, "wechat-decrypt")

EXPORT_DIR = os.path.join(PROJECT_DIR, "export_parse_result")

ALL_KEYS_FILE = os.path.join(EXPORT_DIR, "all_keys.json")
DECRYPTED_DIR = os.path.join(EXPORT_DIR, "decrypted_wechat")
REPORTS_DIR = os.path.join(EXPORT_DIR, "reports_wechat")
LOGS_DIR = os.path.join(EXPORT_DIR, "logs")
IMAGES_DIR = os.path.join(EXPORT_DIR, "decrypted_wechat_images")
DECRYPTED_DINGTALK_DIR = os.path.join(EXPORT_DIR, "decrypted_dingtalk")
WECHAT_DECRYPT_CONFIG = os.path.join(WECHAT_DECRYPT_DIR, "config.json")
