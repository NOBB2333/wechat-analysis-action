"""HTML 报告模板系统。

每个模板是此目录下的一个 Python 模块，需提供：
    NAME: str          – 模板显示名称
    DESCRIPTION: str   – 一句话描述
    render(...) -> str – 返回完整 HTML 文档字符串
"""

import importlib
import os


def list_templates():
    """列出所有可用模板，返回 [(模板id, 名称, 描述), ...] 列表。"""
    templates = []
    template_dir = os.path.dirname(__file__)
    for fname in sorted(os.listdir(template_dir)):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        tid = fname[:-3]
        try:
            mod = importlib.import_module(f".{tid}", package=__package__)
            templates.append((tid, getattr(mod, "NAME", tid), getattr(mod, "DESCRIPTION", "")))
        except Exception:
            continue
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
