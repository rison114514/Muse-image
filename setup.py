#!/usr/bin/env python3
"""
gpt-image-gen 配置向导
用法: python3 setup.py
"""
import os
import sys


CONFIG_FILE = "config.env"
USER_CONFIG_DIR = os.path.expanduser("~/.config/gpt-image-gen")
LOCAL_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASE_URL = "https://your-provider.example.com/gpt-image/v1"


def _read_env_file(path):
    result = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    result[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return result


def _write_config(path, api_key, base_url):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f"GPT_IMAGE_API_KEY={api_key}\n")
        f.write(f"GPT_IMAGE_BASE_URL={base_url}\n")


def _prompt(message, default="", secret=False):
    if default:
        suffix = " [保留现有值，直接回车]" if secret else f" [{default}]"
    else:
        suffix = ""
    try:
        value = input(f"{message}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        sys.exit(0)
    return value or default


def main():
    print("=" * 50)
    print("  gpt-image-gen 配置向导")
    print("=" * 50)
    print()

    # 配置文件位置选择
    local_path = os.path.join(LOCAL_CONFIG_DIR, CONFIG_FILE)
    user_path  = os.path.join(USER_CONFIG_DIR,  CONFIG_FILE)

    print("选择配置文件位置：")
    print(f"  1. 项目本地  ({local_path})")
    print(f"  2. 用户全局  ({user_path})")
    print()
    choice = _prompt("请选择", default="1")
    config_path = local_path if choice != "2" else user_path

    # 读取现有配置
    existing = _read_env_file(config_path)
    current_key = existing.get("GPT_IMAGE_API_KEY", "")
    current_url = existing.get("GPT_IMAGE_BASE_URL", DEFAULT_BASE_URL)

    if current_key:
        masked = current_key[:8] + "..." + current_key[-4:]
        print(f"\n检测到现有配置（API Key: {masked}）")

    print()

    # API Key
    if current_key:
        api_key = _prompt("API Key（直接回车保留）", default=current_key, secret=True)
        if api_key == current_key:
            api_key = current_key  # 保留
    else:
        api_key = _prompt("API Key（必填）").strip()
        while not api_key:
            print("  API Key 不能为空。")
            api_key = _prompt("API Key（必填）").strip()

    # Base URL
    base_url = _prompt("API Base URL", default=current_url)

    # 写入
    _write_config(config_path, api_key, base_url)

    print()
    print(f"✓ 配置已保存：{config_path}")
    print()
    print("快速验证：")
    print(f"  python3 scripts/gen_assets.py --style 01 --prompt \"a test rabbit\"")
    print()
    print("其他配置方式（优先级从高到低）：")
    print("  1. 命令行  --api-key YOUR_KEY --base-url YOUR_URL")
    print("  2. 环境变量  GPT_IMAGE_API_KEY  /  GPT_IMAGE_BASE_URL")
    print(f"  3. 配置文件  {config_path}")


if __name__ == "__main__":
    main()
