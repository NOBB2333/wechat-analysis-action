r"""
自动提取钉钉数字 UID。
从 %APPDATA%\DingTalk\log\*.log 中搜索 uid=xxx 模式。

使用方法:
    python find_dingtalk_uid.py
    # 输出: 691398452
"""
import re
import os
import glob
import sys


def find_uid(log_dir=None):
    """从钉钉日志文件中提取数字 UID"""
    if log_dir is None:
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'DingTalk', 'log')
    
    if not os.path.isdir(log_dir):
        return None
    
    pattern = re.compile(r'uid=(\d{9,10})')
    
    # 优先搜索最新的日志文件
    log_files = sorted(
        glob.glob(os.path.join(log_dir, '*.log*')),
        key=os.path.getmtime,
        reverse=True
    )
    
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    m = pattern.search(line)
                    if m:
                        return m.group(1)
        except:
            continue
    
    return None


def main():
    uid = find_uid()
    if uid:
        print(uid)
    else:
        print("未找到 UID", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
