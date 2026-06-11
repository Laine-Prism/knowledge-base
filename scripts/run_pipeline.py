#!/usr/bin/env python3
"""
知识库采集一键流水线
执行流程：采集 -> 下载 -> 生成摘要 -> 归档
"""

import sys
import os
from pathlib import Path

# 添加脚本目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from wechat_collector import run_once as collect
from summarizer import process_downloads_dir as summarize_and_archive

def run_pipeline():
    """运行完整流水线"""
    print("=" * 50)
    print("  📚 知识库采集流水线")
    print("=" * 50)
    
    # 第一步：采集
    print("\n🔍 第一步：采集新内容...")
    print("-" * 30)
    results = collect()
    
    # 第二步：生成摘要并归档
    print("\n📝 第二步：生成摘要并归档...")
    print("-" * 30)
    summarize_and_archive()
    
    print("\n" + "=" * 50)
    print("  ✅ 流水线执行完毕")
    print("=" * 50)

if __name__ == "__main__":
    run_pipeline()
