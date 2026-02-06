# -*- coding: utf-8 -*-
"""
钉钉多配置智能推送系统（优化版）
✅ 整次运行仅抽取1条图片URL ✅ 所有配置项共享同一URL ✅ 严格校验+降级处理
"""

# 标准库导入
import json
import logging
import os
import re
import time
import random
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# 第三方库导入
from dingtalkchatbot.chatbot import DingtalkChatbot

# =============== 常量定义 ===============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 目录结构定义
CONFIG_DIR = os.path.join(SCRIPT_DIR, "config")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# 确保目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")  # 配置文件路径
IMAGE_URL_FILE = os.path.join(CONFIG_DIR, "image.txt")  # 图片URL文件路径
DEFAULT_TITLE = "医疗安全提醒"  # 默认消息标题
DEFAULT_IMAGE_PLACEHOLDER = "{IMAGE_URL}"  # 默认图片占位符
PUSH_INTERVAL_MIN = 1  # 最小推送间隔（秒）
PUSH_INTERVAL_MAX = 3  # 最大推送间隔（秒）
MAX_RETRIES = 3  # 最大重试次数
INITIAL_RETRY_DELAY = 1  # 初始重试延迟（秒）

# =============== 日志配置 ===============
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename=os.path.join(LOG_DIR, 'run.log'),
    filemode='a'
    ,encoding='utf-8'
)
logger = logging.getLogger(__name__)


class DingTalkBotEnhanced:
    """增强版钉钉机器人：支持多配置、统一图片URL、重试机制"""
    
    # 钉钉允许的图片域名白名单
    WHITELIST_DOMAINS = ["alicdn.com", "qiniucdn.com", "aliyuncs.com", 
                        "cdn.", "img.", "oss-", "yourcompany.com"]
    
    # 钉钉屏蔽的域名列表
    BLOCKED_DOMAINS = ["github.com", "raw.githubusercontent.com", 
                      "localhost", "127.0.0.1"]
    
    # 支持的图片格式
    SUPPORTED_IMAGE_FORMATS = ["jpg", "jpeg", "png", "gif", "webp"]
    
    # 非法字符
    ILLEGAL_CHARACTERS = [" ", "|", "{", "}"]

    def __init__(self, webhook: str, secret: Optional[str] = None):
        """初始化钉钉机器人
        
        Args:
            webhook: 钉钉机器人webhook地址
            secret: 钉钉机器人加签密钥（可选）
            
        Raises:
            ValueError: 当webhook不包含access_token时
        """
        if "access_token" not in webhook:
            raise ValueError("❌ Webhook必须包含access_token")
        
        self.bot = DingtalkChatbot(webhook, secret=secret)
        logger.info("✅ 钉钉机器人初始化成功 | 加签: %s", "已启用" if secret else "未启用")

    @staticmethod
    def validate_image_url(url: str) -> tuple[bool, str]:
        """严格校验图片URL合规性
        
        Args:
            url: 待校验的图片URL
            
        Returns:
            tuple[bool, str]: (是否有效, 校验结果消息)
        """
        # 检查是否为HTTPS协议
        if not url.startswith("https://"):
            return False, "❌ 非HTTPS协议（钉钉强制拦截HTTP）"
        
        # 检查是否包含被屏蔽的域名
        if any(block in url.lower() for block in DingTalkBotEnhanced.BLOCKED_DOMAINS):
            return False, "❌ 域名被钉钉屏蔽（如GitHub Raw）"
        
        # 检查是否在推荐白名单中
        if not any(domain in url for domain in DingTalkBotEnhanced.WHITELIST_DOMAINS):
            logger.warning("⚠️ 域名未在推荐白名单中（可能无法显示）: %s", url)
        
        # 检查文件格式
        if not re.search(
            r"\.(" + "|".join(DingTalkBotEnhanced.SUPPORTED_IMAGE_FORMATS) + r")$", 
            url, 
            re.IGNORECASE
        ):
            return False, "❌ 非标准图片格式（需.jpg/.png等）"
        
        # 检查非法字符
        if any(char in url for char in DingTalkBotEnhanced.ILLEGAL_CHARACTERS):
            return False, "❌ URL含非法字符（需URL编码）"
        
        return True, "✅ URL校验通过"

    def send_markdown_with_image(self, 
                                title: str, 
                                content: str, 
                                img_url: str, 
                                image_placeholder: str = DEFAULT_IMAGE_PLACEHOLDER, 
                                at_mobiles: Optional[List[str]] = None, 
                                is_at_all: bool = False) -> bool:
        """使用外部提供的图片URL发送Markdown消息
        
        Args:
            title: 消息标题
            content: 消息内容（支持Markdown格式）
            img_url: 图片URL
            image_placeholder: 内容中图片URL的占位符
            at_mobiles: 要@的手机号列表
            is_at_all: 是否@所有人
            
        Returns:
            bool: 发送是否成功
        """
        # 1. 校验传入的URL
        is_valid, msg = self.validate_image_url(img_url)
        if not is_valid:
            logger.error(msg)
            return False
        logger.info(msg)

        # 2. 替换占位符或追加图片
        if image_placeholder in content:
            content = content.replace(image_placeholder, img_url)
            logger.debug("🖼️ 已替换占位符为: %s", img_url)
        else:
            content += f"\n\n![监控图]({img_url})"
            logger.debug("📎 无占位符，图片已追加到末尾")

        # 3. 发送Markdown（带重试机制）
        return self._send_with_retry(
            method=self.bot.send_markdown,
            title=title,
            text=content,
            at_mobiles=at_mobiles if not is_at_all else None,
            is_at_all=is_at_all
        )

    def _send_with_retry(self, method, **kwargs) -> bool:
        """带重试机制的发送方法
        
        Args:
            method: 要调用的发送方法
            **kwargs: 方法参数
            
        Returns:
            bool: 发送是否成功
        """
        for retry in range(MAX_RETRIES):
            try:
                res = method(**kwargs)
                
                # 检查是否发送成功
                if isinstance(res, dict) and res.get("errcode") == 0:
                    logger.info("✅ 消息发送成功 | Webhook: %s", self.bot.webhook[-20:])
                    return True
                else:
                    err = res.get("errmsg", "未知错误") if isinstance(res, dict) else str(res)
                    logger.error("❌ 发送失败: %s | Webhook: %s", err, self.bot.webhook[-20:])
                    
                    # 如果不是最后一次重试，等待后继续
                    if retry < MAX_RETRIES - 1:
                        delay = INITIAL_RETRY_DELAY * (2 ** retry) + random.uniform(0, 1)
                        logger.info("⏳ 等待 %.2f 秒后重试...", delay)
                        time.sleep(delay)
                    
            except Exception as e:
                logger.error("❌ 发送过程异常: %s | Webhook: %s", str(e), self.bot.webhook[-20:])
                
                # 如果不是最后一次重试，等待后继续
                if retry < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** retry) + random.uniform(0, 1)
                    logger.info("⏳ 等待 %.2f 秒后重试...", delay)
                    time.sleep(delay)
        
        return False

    def send_text(self, 
                 msg: str, 
                 at_mobiles: Optional[List[str]] = None, 
                 is_at_all: bool = False) -> bool:
        """发送文本消息
        
        Args:
            msg: 消息内容
            at_mobiles: 要@的手机号列表
            is_at_all: 是否@所有人
            
        Returns:
            bool: 发送是否成功
        """
        final_msg = ("@所有人 " if is_at_all else " ".join([f"@{m}" for m in at_mobiles]) + " ") + msg \
                  if (is_at_all or at_mobiles) else msg
        
        return self._send_with_retry(
            method=self.bot.send_text,
            msg=final_msg,
            at_mobiles=at_mobiles,
            is_at_all=is_at_all
        )

    @staticmethod
    def pop_first_url(file_path: str) -> Optional[str]:
        """原子操作：弹出文件首行URL
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: 弹出的URL，如果文件为空或不存在则返回None
        """
        if not os.path.exists(file_path):
            logger.error("❌ URL文件不存在: %s", file_path)
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 使用列表推导式过滤空行并去除首尾空白
                lines = [line.strip() for line in f if line.strip()]
            
            if not lines:
                logger.warning("⚠️ URL文件为空")
                return None
            
            # 获取首行URL并准备剩余行
            current_url = lines[0]
            remaining = lines[1:]
            
            # 使用临时文件原子性替换原文件
            temp_path = file_path + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                if remaining:
                    f.write('\n'.join(remaining) + '\n')
            
            os.replace(temp_path, file_path)
            logger.info("✅ 已弹出URL: %s | 剩余: %d", current_url, len(remaining))
            return current_url
            
        except Exception as e:
            logger.error("❌ 读取URL文件失败: %s", str(e))
            return None


@contextmanager
def change_working_dir(path: str):
    """上下文管理器：临时切换工作目录
    
    Args:
        path: 要切换到的目录路径
    """
    original_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_dir)


def load_config() -> List[Dict[str, Any]]:
    """加载并验证配置文件
    
    Returns:
        List[Dict[str, Any]]: 配置列表
        
    Raises:
        FileNotFoundError: 当配置文件不存在时
        ValueError: 当配置文件格式不正确时
    """
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"配置文件 {CONFIG_FILE} 不存在")

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    if not isinstance(config, list):
        raise ValueError("配置文件应为列表格式")

    # 验证每个配置项
    required_fields = ['webhook', 'secret', 'template']
    valid_config = []
    
    for idx, item in enumerate(config):
        if not isinstance(item, dict):
            logger.warning("⚠️ 第 %d 项不是字典格式，已跳过", idx + 1)
            continue
        
        missing = [k for k in required_fields if k not in item]
        if missing:
            logger.warning("⚠️ 第 %d 项缺少字段: %s，已跳过", idx + 1, ', '.join(missing))
            continue
        
        # 添加默认值
        item.setdefault('title', DEFAULT_TITLE)
        item.setdefault('at_mobiles', [])
        item.setdefault('is_at_all', False)
        
        valid_config.append(item)

    logger.info(f"✅ 成功加载 %d/%d 个有效配置项", len(valid_config), len(config))
    return valid_config


def main() -> int:
    """主流程：整次运行仅抽取1条图片URL
    
    Returns:
        int: 程序退出码（0表示成功，非0表示失败）
    """
    try:
        # 切换到脚本所在目录
        with change_working_dir(SCRIPT_DIR):
            logger.info("🚀 钉钉每日推送脚本启动")
            
            # 1. 获取图片URL
            img_url = DingTalkBotEnhanced.pop_first_url(IMAGE_URL_FILE)
            if not img_url:
                logger.error("❌ 无法获取图片URL，请检查文件: %s", IMAGE_URL_FILE)
                return 1
            logger.info("🎯 本次运行统一使用图片URL: %s", img_url)
            
            # 2. 加载配置
            config = load_config()
            if not config:
                logger.error("❌ 没有有效配置项，程序退出")
                return 1
            
            # 3. 遍历所有配置项发送消息
            success_count = 0
            
            for idx, item in enumerate(config, 1):
                logger.info("\n[+] 处理第 %d 个配置项（Webhook: %s...）", idx, item['webhook'][:30])

                try:
                    bot = DingTalkBotEnhanced(webhook=item['webhook'], secret=item['secret'])

                    if bot.send_markdown_with_image(
                        title=item['title'], 
                        content=item['template'],
                        img_url=img_url,
                        image_placeholder=DEFAULT_IMAGE_PLACEHOLDER,
                        at_mobiles=item['at_mobiles'],
                        is_at_all=item['is_at_all']
                    ):
                        success_count += 1
                except Exception as e:
                    logger.error("❌ 处理第 %d 项时出错: %s | Webhook: %s", 
                               idx, str(e), item['webhook'][-10:])
                    continue

                # 添加随机延迟，避免频繁调用钉钉接口被限流
                delay = random.uniform(PUSH_INTERVAL_MIN, PUSH_INTERVAL_MAX)
                logger.debug("⏳ 等待 %.2f 秒后处理下一个配置项", delay)
                time.sleep(delay)

            logger.info("\n[√] 任务完成！成功发送 %d/%d 条消息（共用1张图片）", success_count, len(config))
            
            # 4. 如果有发送失败的消息，记录告警
            if success_count < len(config):
                logger.warning("⚠️ 部分消息发送失败，请检查日志")
                
            logger.info("✅ 程序正常退出")
            return 0

    except Exception as e:
        logger.error("❌ 主程序异常: %s", str(e))
        return 1


if __name__ == "__main__":
    # 在Windows系统下设置stdout编码为utf-8
    if os.name == 'nt':
        import sys
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    exit(main())