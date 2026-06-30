"""HTML 报告模板系统。

每个模板是此目录下的一个 Python 模块，需提供：
    NAME: str          – 模板显示名称
    DESCRIPTION: str   – 一句话描述
    render(...) -> str – 返回完整 HTML 文档字符串
"""

import importlib
import os
import sys


def _get_template_dir():
    """获取模板目录路径，兼容 PyInstaller 打包环境。

    PyInstaller 打包后，模板 .py 文件被编译进 PYZ archive，
    无法通过文件系统列出。此时使用预注册的模板列表。
    """
    d = os.path.dirname(__file__)
    if os.path.isdir(d):
        py_files = [f for f in os.listdir(d) if f.endswith('.py') and not f.startswith('_')]
        if py_files:
            return d
    # PyInstaller 打包后：检查 src/templates
    import sys as _sys
    base = os.path.dirname(_sys.executable) if getattr(_sys, 'frozen', False) else ''
    for sub in ('src\\templates', 'templates'):
        c = os.path.join(base, sub)
        if os.path.isdir(c):
            py_files = [f for f in os.listdir(c) if f.endswith('.py') and not f.startswith('_')]
            if py_files:
                return c
    return d


# 预注册的模板列表（PyInstaller 打包后文件系统不可用时使用）
_TEMPLATE_REGISTRY = {
    'default': ('default', '极简白', '简洁清爽的白色主题'),
    'stock': ('stock', '股票终端', '红绿配色的股票行情终端风格'),
    'anime': ('anime', '二次元', '动漫风格的粉色主题'),
    'terminal': ('terminal', '黑客终端', '黑色背景绿色文字的终端风格'),
    'scrapbook': ('scrapbook', '手账剪贴簿', '温馨手账风格的拼贴主题'),
}


def list_templates():
    """列出所有可用模板，返回 [(模板id, 名称, 描述), ...] 列表。"""
    template_dir = _get_template_dir()
    try:
        files = os.listdir(template_dir)
    except (FileNotFoundError, NotADirectoryError):
        # PyInstaller 打包后无法列出目录，使用预注册列表
        return [(tid, name, desc) for tid, (_, name, desc) in _TEMPLATE_REGISTRY.items()]

    templates = []
    for fname in sorted(files):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        tid = fname[:-3]
        try:
            mod = importlib.import_module(f".{tid}", package=__package__)
            name = getattr(mod, "NAME", tid)
            desc = getattr(mod, "DESCRIPTION", "")
        except Exception:
            # fallback to registry
            entry = _TEMPLATE_REGISTRY.get(tid)
            if entry:
                _, name, desc = entry
            else:
                continue
        templates.append((tid, name, desc))
    return templates


def get_template(name):
    """根据模板 id 导入并返回模板模块。"""
    return importlib.import_module(f".{name}", package=__package__)


def render_template(name, group_name, date_str, stats, topics, user_titles,
                    quote=None, top_users_count=9, evidence_per_topic=3):
    """使用指定模板渲染 HTML 报告字符串。"""
    mod = get_template(name)
    return mod.render(
        group_name=group_name,
        date_str=date_str,
        stats=stats,
        topics=topics,
        user_titles=user_titles,
        quote=quote,
        top_users_count=top_users_count,
        evidence_per_topic=evidence_per_topic,
    )


DEFAULT_TEMPLATE = "default"
