"""把生成的 PNG 日报图片发送到微信群聊。

依赖: pywin32, pyautogui, Pillow

流程:
1. 激活微信窗口（FindWindow + SwitchToThisWindow，兜底 Ctrl+Alt+W）
2. 搜索群聊（Ctrl+F → 清空 → 输入群名 → Enter）
3. 检测输入框是否有内容（Ctrl+A → Ctrl+C → 检查剪贴板）
4. 为空: 复制 PNG 到剪贴板 → Ctrl+V → Enter 发送
5. 非空: 打印提示，跳过发送
"""
from __future__ import annotations

import ctypes
import io
import logging
import os
import time

import pyautogui
import win32clipboard
import win32con
import win32gui
from PIL import Image

logger = logging.getLogger(__name__)

# 微信主窗口类名（按可能性从高到低排列）
_WECHAT_CLASSES = ["WeChatMainWndForPC", "ChatWnd", "WeChat"]

_PAUSE = 0.3


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------

def _find_wechat_window():
    """查找微信主窗口，返回句柄；找不到返回 None。"""
    for cls in _WECHAT_CLASSES:
        hwnd = win32gui.FindWindow(cls, None)
        if hwnd:
            return hwnd
    return win32gui.FindWindow(None, "微信")


def _activate_wechat() -> bool:
    """把微信窗口激活到前台。成功返回 True。

    用 SwitchToThisWindow 替代 SetForegroundWindow，因为后者在
    现代 Windows 上对后台进程有严格的 UIPI 限制（无法可靠地置前台）。
    完成后会检查实际前景窗口是否真的是微信。
    """
    hwnd = _find_wechat_window()
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
        time.sleep(_PAUSE)

        # 验证微信是否真的成了前景窗口
        foreground = win32gui.GetForegroundWindow()
        if foreground != hwnd:
            # 可能原因：微信以管理员身份运行，而终端不是
            logger.warning(
                "激活后前景窗口 (%s) 不是微信 (%s)，"
                "键盘模拟可能无效。如微信以管理员身份运行，"
                "请也用管理员身份运行此脚本。",
                win32gui.GetWindowText(foreground) or hex(foreground),
                win32gui.GetWindowText(hwnd) or hex(hwnd),
            )
        return True

    # 兜底：模拟 Ctrl+Alt+W 热键（部分第三方微信助手注册的热键）
    logger.info("未找到微信窗口，尝试 Ctrl+Alt+W 热键 …")
    pyautogui.hotkey("ctrl", "alt", "w")
    time.sleep(1)
    hwnd = _find_wechat_window()
    if hwnd:
        ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
        time.sleep(_PAUSE)
        return True
    return False


def _search_group(group_name: str) -> None:
    """Ctrl+F 聚焦搜索栏 → 粘贴群名（剪贴板）→ 回车选中第一个结果。

    用粘贴代替逐个按键，因为部分系统上 pyautogui.write() 可能
    无法可靠地把文字输入到微信的搜索输入框。粘贴方案更稳定。
    """
    # 先把群名写入剪贴板
    prev_clipboard = _get_clipboard_text()
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(group_name, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    time.sleep(0.05)

    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.5)                     # 等搜索 UI 完全出现
    pyautogui.hotkey("ctrl", "a")       # 全选清空已有文字
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")       # 从剪贴板粘贴群名
    time.sleep(_PAUSE)                  # 等搜索结果刷新
    pyautogui.press("enter")
    time.sleep(_PAUSE)

    # 恢复剪贴板
    if prev_clipboard:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(prev_clipboard, win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()


def _get_clipboard_text() -> str | None:
    """读取剪贴板文本，没有文本时返回 None。"""
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                raw = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                return raw.decode("utf-8", errors="replace")
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None


def _focus_chat_input() -> None:
    """点击微信聊天输入框区域，确保键盘焦点落对位置。

    搜索切群后焦点可能留在消息列表，不点一下输入框的话
    Ctrl+V 粘贴和 Ctrl+A/Ctrl+C 检测都无效。
    """
    hwnd = _find_wechat_window()
    if not hwnd:
        return
    rect = win32gui.GetWindowRect(hwnd)
    win_w = rect[2] - rect[0]
    win_h = rect[3] - rect[1]
    # 输入框在窗口右下区域：x 偏中点（越过左侧群列表），y 靠底部
    cx = rect[0] + int(win_w * 0.55)
    cy = rect[1] + int(win_h * 0.85)
    pyautogui.click(cx, cy)
    time.sleep(0.2)


def _check_input_has_content() -> bool:
    """清剪贴板 → Ctrl+A → Ctrl+C 探测输入框有无文字或图片。

    调用前需确保焦点已在输入框（由 _focus_chat_input 负责）。
    返回 True 表示输入框有内容（跳过发送），False 表示为空（安全粘贴）。
    """
    # 1. 先清空剪贴板，确保后续的内容一定来自输入框
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.CloseClipboard()
    time.sleep(0.05)

    # 2. 全选 + 复制
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.15)

    # 3. 检查文本
    new_text = _get_clipboard_text()
    if new_text and new_text.strip():
        return True

    # 4. 检查图片（微信输入框里的图片复制出来是 CF_DIB 或 CF_BITMAP）
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                return True
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_BITMAP):
                return True
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        pass

    return False


def _copy_image_to_clipboard(image_path: str) -> None:
    """把 PNG 图片以 CF_DIB 格式写入剪贴板。

    效果等同于浏览器"复制图片"或截图，微信里粘贴出来是内联图片，
    不是文件附件。
    """
    img = Image.open(image_path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    # BMP 文件 = 14 字节 BITMAPFILEHEADER + DIB（BITMAPINFOHEADER + 像素数据）
    dib_data = buf.getvalue()[14:]
    buf.close()

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, dib_data)
    finally:
        win32clipboard.CloseClipboard()


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def send_image_to_group(image_path: str, group_name: str) -> bool:
    """把 PNG 图片发送到微信群聊。

    Args:
        image_path: PNG 文件路径（绝对或相对路径均可）。
        group_name: 目标群聊的显示名称，如 ``"家"``。

    Returns:
        ``True``  → 图片已粘贴并发送成功。
        ``False`` → 输入框有内容，跳过发送（stdout 会打印原因）。

    Raises:
        FileNotFoundError: *image_path* 文件不存在。
        RuntimeError: 无法激活微信窗口。
    """
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    # ---- 第 1 步：激活微信窗口 ------------------------------------------------
    print("[SEND] 激活微信窗口 …")
    if not _activate_wechat():
        raise RuntimeError("无法激活微信窗口，请检查微信是否已启动")

    # ---- 第 2 步：搜索并选中目标群聊 ------------------------------------------
    print(f"[SEND] 搜索群聊: {group_name}")
    _search_group(group_name)

    # ---- 第 3 步：点击输入框激活焦点 ------------------------------------------
    print("[SEND] 激活输入框 …")
    _focus_chat_input()

    # ---- 第 4 步：检测输入框是否已有文字 --------------------------------------
    print("[SEND] 检测输入框是否有内容 …")
    if _check_input_has_content():
        print(f"[SEND] ⚠ 群「{group_name}」输入框非空，跳过发送")
        return False

    # ---- 第 5 步：复制图片到剪贴板，粘贴并发送 --------------------------------
    print(f"[SEND] 复制图片到剪贴板: {image_path}")
    _copy_image_to_clipboard(image_path)
    time.sleep(0.1)

    print("[SEND] 粘贴并发送 …")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(_PAUSE)           # 等粘贴完成
    # pyautogui.press("enter")
    # time.sleep(_PAUSE)

    print(f"[SEND] ✅ 已发送图片到群「{group_name}」")
    return True
