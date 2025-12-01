#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Channel Scraper for @news6551
爬取公开频道的 CEX listing 信息
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
except ImportError:
    print("请先安装 telethon: pip install telethon")
    exit(1)

# 尝试从配置文件导入
try:
    from config import API_ID, API_HASH, CHANNEL_USERNAME, MESSAGE_LIMIT
except ImportError:
    # 如果没有配置文件，使用默认值
    API_ID = 'YOUR_API_ID'  # 请替换为你的 API ID
    API_HASH = 'YOUR_API_HASH'  # 请替换为你的 API Hash
    CHANNEL_USERNAME = 'news6551'  # 频道用户名
    MESSAGE_LIMIT = 2000  # 默认获取2000条消息（增加以获取更多 Alpha Coin）

# 会话文件
SESSION_FILE = 'telegram_session.session'

# 输出文件
OUTPUT_JSON = 'cex_listings.json'
OUTPUT_JS = 'data.js'


def extract_listing_info(text, message_date=None):
    """
    从消息文本中提取 CEX listing 信息
    只提取 new listing，过滤掉活动相关的消息
    
    Args:
        text: 消息文本
        message_date: 消息发布日期（可选），用于 Alpha Coin 等没有明确日期的消息
    """
    listings = []
    
    text_lower = text.lower()
    
    # 优先过滤掉 delist（下架）相关的消息，无论是否包含 listing 关键词
    delist_keywords = [
        r'\bdelisting\b', r'\bdelist\b', r'下架', r'removal', r'暂停交易', r'suspend.*trading',
        r'停止交易', r'停止.*交易', r'终止.*交易', r'取消.*交易', r'remove.*trading',
        r'will.*delist', r'to.*delist', r'going.*to.*delist', r'停止.*上市'
    ]
    
    # 如果包含 delist 关键词，直接返回空列表
    if any(re.search(keyword, text_lower) for keyword in delist_keywords):
        return listings
    
    # 先检查是否是 listing 消息（优先级最高）
    is_listing = re.search(r'\blisting\b|\blist\b|上市|上线|alpha\s+coin|new.*coin|add.*trading', text_lower)
    
    # 过滤掉纯活动/促销消息（但如果同时是 listing，则保留）
    exclude_keywords = [
        r'^.*campaign\s*$', r'^.*promotion\s*$', r'^.*contest\s*$', r'^.*giveaway\s*$',
        r'^.*bonus\s*$', r'^.*discount\s*$', r'^.*reward\s*$',
        r'maintenance', r'upgrade'
    ]
    
    # 如果是 listing 消息，即使包含活动关键词也保留（比如 listing + 空投活动）
    # 但如果是纯活动消息（没有 listing），则过滤
    if not is_listing:
        # 检查是否是纯活动消息
        is_pure_activity = any(re.search(keyword, text_lower) for keyword in [
            r'^.*airdrop\s*$', r'^.*空投\s*$', r'^.*campaign\s*$', r'^.*promotion\s*$',
            r'^.*giveaway\s*$', r'^.*contest\s*$', r'^.*reward\s*$'
        ])
        if is_pure_activity:
            return listings
    
    # 必须包含 listing 相关的关键词（放宽条件，包括更多变体）
    listing_keywords = [
        r'\blisting\b', r'\blist\b', r'上市', r'上线', r'add.*spot', r'add.*perpetual',
        r'new.*trading', r'launch.*trading', r'will.*list', r'to.*list',
        r'list.*spot', r'list.*perpetual', r'list.*perp', r'add.*trading',
        r'opens.*trading', r'start.*trading', r'available.*trading',
        r'alpha\s+coin', r'new.*coin', r'introducing.*on', r'마켓.*추가', r'新增.*资产',
        r'important\s+notice.*list', r'重要通知.*上线'
    ]
    
    # 检查是否包含 listing 关键词
    if not any(re.search(keyword, text_lower) for keyword in listing_keywords):
        return listings
    
    # 必须包含交易所名称（扩展更多交易所，包括韩文交易所）
    exchange_patterns = [
        r'\b(binance|coinbase|okx|okex|kraken|bybit|huobi|gate\.io|gateio|kucoin|bitfinex|bitstamp|mexc|bitget|bitmart|coinlist|gemini|bithumb|upbit|hyperliquid)\b',
        r'(币安|欧易|火币|gate|库币)',  # 中文交易所名称
    ]
    
    exchanges = []
    exchange_map = {
        '币安': 'Binance',
        '欧易': 'OKX',
        '火币': 'Huobi',
        'gate': 'Gate',
        '库币': 'KuCoin',
    }
    
    for pattern in exchange_patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            # 如果是中文交易所名称，转换为英文
            if match in exchange_map:
                exchanges.append(exchange_map[match].lower())
            else:
                exchanges.append(match)
    
    if not exchanges:
        return listings
    
    # 识别交易类型：perp（永续合约）、spot（现货）、alpha 或 pre-market
    # 一条消息可能同时包含多个类型，需要识别所有类型
    listing_types = []
    
    # Pre-Market 检测（优先级最高，因为它是特殊的市场类型）
    is_premarket = re.search(r'pre-market|premarket|预上市|预市', text_lower)
    
    # Coinbase 默认都是 spot
    if 'coinbase' in text_lower:
        if is_premarket:
            listing_types.append('pre-market')
        else:
            listing_types.append('spot')
    # Binance Alpha Coin（优先级最高，如果是 Alpha Coin，只识别为 alpha 类型）
    # 暂时过滤掉 Alpha Coin，只保留其他类型的 listing
    is_alpha_coin = re.search(r'new\s+binance\s+alpha\s+coin|binance\s+alpha\s+coin|alpha\s+coin|binance\s+alpha', text_lower)
    if is_alpha_coin:
        # 如果是 Alpha Coin，直接返回空列表（不提取）
        return []
    # Pre-Market Perpetual（非 Alpha Coin）
    elif is_premarket and re.search(r'perpetual|perp|futures|永续|合约', text_lower):
        listing_types.append('pre-market')
    # Pre-Market Spot（非 Alpha Coin）
    elif is_premarket:
        listing_types.append('pre-market')
    # Perp 相关关键词（非 Pre-Market，非 Alpha Coin）
    elif re.search(r'perpetual\s+futures|perpetual\s+contract|perp\s+contract|永续合约|futures.*perpetual|contract.*api|合约.*api', text_lower):
        listing_types.append('perp')
    # Bybit Convert 是 spot
    elif re.search(r'convert', text_lower) and 'bybit' in text_lower:
        listing_types.append('spot')
    # Bybit contract 是 perp
    elif re.search(r'contract', text_lower) and 'bybit' in text_lower and 'convert' not in text_lower:
        listing_types.append('perp')
    # Binance Futures 是 perp（但如果是 Alpha Coin，已经识别为 alpha 了）
    elif re.search(r'binance\s+futures|futures.*will\s+launch', text_lower) and not is_alpha_coin:
        listing_types.append('perp')
    # Binance Earn/Buy/Convert/Margin 是 spot（但如果是 Alpha Coin，已经识别为 alpha 了）
    elif re.search(r'earn|buy\s+crypto|convert.*margin|margin', text_lower) and 'binance' in text_lower and not is_alpha_coin:
        listing_types.append('spot')
    # OKX spot trading
    elif re.search(r'spot\s+trading|list.*for\s+spot', text_lower) and 'okx' in text_lower:
        listing_types.append('spot')
    # OKX perpetual futures（非 pre-market）
    elif re.search(r'perpetual\s+futures|list.*perpetual', text_lower) and 'okx' in text_lower and not is_premarket:
        listing_types.append('perp')
    # Hyperliquid 永续合约
    elif re.search(r'永续合约', text_lower) and 'hyperliquid' in text_lower:
        listing_types.append('perp')
    # 其他 perp 关键词（非 Pre-Market）
    elif re.search(r'perpetual|perp|futures|swap|合约', text_lower) and 'spot' not in text_lower and not is_premarket:
        if 'perp' not in listing_types:
            listing_types.append('perp')
    # 其他 spot 关键词
    elif re.search(r'spot|现货|roadmap|마켓.*추가|新增.*资产', text_lower):
        if 'spot' not in listing_types:
            listing_types.append('spot')
    
    # 如果没有识别到任何类型，默认是 spot
    if not listing_types:
        listing_types = ['spot']
    
    # 提取日期（多种格式，优先提取消息中的日期）
    date_patterns = [
        # ISO 格式（优先，因为更准确）
        r'(\d{4})[-\/](\d{1,2})[-\/](\d{1,2})',  # 2024-12-15 或 2024/12/15
        # 英文月份格式 - 支持逗号
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\s\.\/,-]+(\d{1,2})[\s\.\/,-]+(\d{4})',  # Oct 23, 2025 或 Oct 23 2025
        r'(\d{1,2})[\s\.\/,-]+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\s\.\/,-]+(\d{4})',  # 23 Oct 2025
        # 中文日期格式
        r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',  # 2025年11月14日
        # 其他格式
        r'(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})',  # 12-15-2024
        r'(\d{1,2})\s+月\s+(\d{1,2})\s+日',      # 12月15日
    ]
    
    date_match = None
    for pattern in date_patterns:
        # 使用原始文本（不转小写）来匹配日期，因为英文月份名称需要保持大小写
        # 但对于已经转小写的模式（如月份名称），使用 text_lower
        if 'jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec' in pattern.lower():
            date_match = re.search(pattern, text_lower)
        else:
            date_match = re.search(pattern, text)
        if date_match:
            break
    
    # 提取代币名称（通常是大写字母组合，排除常见单词）
    exclude_tokens = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS', 'HIM', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WHO', 'WAY', 'USE', 'HER', 'SHE', 'PUT', 'END', 'WHY', 'ASK', 'MEN', 'TURN', 'WANT', 'TELL', 'WENT', 'WERE', 'WHAT', 'WHEN', 'WITH', 'YOUR', 'FROM', 'HAVE', 'THIS', 'THAT', 'WILL', 'MORE', 'VERY', 'WHAT', 'KNOW', 'JUST', 'LIKE', 'LONG', 'MAKE', 'MANY', 'OVER', 'SUCH', 'TAKE', 'THAN', 'THEM', 'WELL', 'WERE', 'WILL', 'YEAR', 'YOUR', 'ABOUT', 'AFTER', 'AGAIN', 'BEING', 'BELOW', 'BETWEEN', 'BOTH', 'CAME', 'CARRY', 'CHANGE', 'CHILDREN', 'CLOSE', 'COME', 'COULD', 'DOES', 'DON\'T', 'DURING', 'EACH', 'EARLY', 'EARTH', 'EIGHT', 'EVERY', 'EXAMPLE', 'EYES', 'FACE', 'FAMILY', 'FAR', 'FATHER', 'FEET', 'FEW', 'FIND', 'FIRST', 'FOUND', 'FOUR', 'GAVE', 'GET', 'GIRL', 'GIVE', 'GOES', 'GOOD', 'GOT', 'GREAT', 'GROUP', 'GROW', 'HAD', 'HAND', 'HARD', 'HAS', 'HAVE', 'HEAD', 'HEAR', 'HELP', 'HERE', 'HIGH', 'HOME', 'HOUR', 'HOUSE', 'HOW', 'INTO', 'ITS', 'JUST', 'KEEP', 'KIND', 'KNEW', 'KNOW', 'LARGE', 'LAST', 'LATE', 'LEARN', 'LEFT', 'LESS', 'LIFE', 'LIGHT', 'LINE', 'LIST', 'LITTLE', 'LIVE', 'LONG', 'LOOK', 'LOOKED', 'MADE', 'MAKE', 'MAN', 'MANY', 'MAY', 'MEAN', 'MEN', 'MIGHT', 'MILES', 'MISS', 'MONEY', 'MORNING', 'MOST', 'MOTHER', 'MOVE', 'MUCH', 'MUST', 'NAME', 'NEAR', 'NEED', 'NEVER', 'NEW', 'NEXT', 'NIGHT', 'NOON', 'NOTE', 'NOTHING', 'NOW', 'NUMBER', 'OFF', 'OFTEN', 'ONCE', 'ONLY', 'OPEN', 'ORDER', 'OTHER', 'OUR', 'OUT', 'OVER', 'OWN', 'PAGE', 'PAPER', 'PART', 'PASS', 'PAST', 'PEOPLE', 'PER', 'PICTURE', 'PLACE', 'PLAN', 'PLAY', 'POINT', 'PUT', 'READ', 'REAL', 'RIGHT', 'ROOM', 'ROUND', 'SAID', 'SAME', 'SAW', 'SAY', 'SCHOOL', 'SEA', 'SECOND', 'SEE', 'SEEM', 'SENT', 'SET', 'SHE', 'SHIP', 'SHORT', 'SHOULD', 'SHOW', 'SIDE', 'SINCE', 'SING', 'SIT', 'SIX', 'SIZE', 'SLOW', 'SMALL', 'SOON', 'SOUND', 'SOUTH', 'SPACE', 'SPEAK', 'SPELL', 'STAND', 'START', 'STATE', 'STILL', 'STOP', 'STORY', 'SUCH', 'SURE', 'TAKE', 'TALK', 'TELL', 'TEN', 'TEST', 'THAN', 'THAT', 'THEIR', 'THEM', 'THEN', 'THERE', 'THESE', 'THEY', 'THING', 'THINK', 'THIS', 'THOSE', 'THREE', 'THROUGH', 'TIME', 'TOLD', 'TOOK', 'TOO', 'TOOK', 'TOOL', 'TOP', 'TOWARD', 'TOWN', 'TREE', 'TRIED', 'TRUE', 'TRY', 'TURN', 'TWO', 'UNDER', 'UNTIL', 'UPON', 'USED', 'USING', 'USUAL', 'VALUE', 'VERY', 'VOICE', 'WALK', 'WANT', 'WARM', 'WATCH', 'WATER', 'WAVE', 'WAYS', 'WEAR', 'WEEK', 'WEIGHT', 'WELL', 'WENT', 'WERE', 'WEST', 'WHAT', 'WHEEL', 'WHEN', 'WHERE', 'WHICH', 'WHILE', 'WHITE', 'WHO', 'WHOLE', 'WHOSE', 'WHY', 'WIDE', 'WIFE', 'WILD', 'WILL', 'WIND', 'WINDOW', 'WISH', 'WITH', 'WITHIN', 'WITHOUT', 'WOMAN', 'WOMEN', 'WON\'T', 'WONDER', 'WOOD', 'WORD', 'WORE', 'WORK', 'WORLD', 'WOULD', 'WRITE', 'WRONG', 'WROTE', 'YARD', 'YEAR', 'YELLOW', 'YES', 'YESTERDAY', 'YET', 'YOU', 'YOUNG', 'YOUR', 'YOURSELF'}
    
    # 提取代币名称（更精确的模式，支持更多格式）
    # 注意：更具体的模式要放在前面
    token_patterns = [
        # 特定格式：list pre-market perpetual futures for TOKEN (Name) - 最具体
        r'list\s+pre-market\s+perpetual\s+futures\s+for\s+([A-Z]{2,10})\s*\(([A-Z][A-Za-z]+)\)',  # "list pre-market perpetual futures for SENT (Sentient)"
        r'to\s+list\s+pre-market\s+perpetual\s+futures\s+for\s+([A-Z]{2,10})\s*\(([A-Z][A-Za-z]+)\)',  # "to list pre-market perpetual futures for SENT (Sentient)"
        # 特定格式：list perpetual futures for TOKEN (Name)
        r'list\s+perpetual\s+futures\s+for\s+([A-Z]{2,10})\s*\(([A-Z][A-Za-z]+)\)',  # "list perpetual futures for TOKEN (Name)"
        # 优先匹配带括号的格式，如 "Rayls (RLS)" 或 "APRO (AT)" 或 "SENT (Sentient)"
        r'([A-Z][A-Za-z]+)\s*\(([A-Z]{2,10})\)',  # "Rayls (RLS)" 或 "APRO (AT)"
        r'([A-Z]{2,10})\s*\(([A-Z][A-Za-z]+)\)',  # "SENT (Sentient)" - 代币代码在前
        # 特定格式：list perpetual futures for TOKEN
        r'list\s+perpetual\s+futures\s+for\s+([A-Z]{2,10})',  # "list perpetual futures for SEI"
        r'to\s+list\s+perpetual\s+futures\s+for\s+([A-Z]{2,10})',  # "to list perpetual futures for SEI"
        r'list\s+([A-Z]{2,10})\s+for\s+spot',  # "list SEI for spot"
        r'list\s+([A-Z]{2,10})\s+for\s+perpetual',  # "list SEI for perpetual"
        # 中文格式：上线TOKEN（Name）代币的预市永续期货
        r'上线([A-Z]{2,10})\s*\(([A-Z][A-Za-z]+)\)',  # "上线SENT（Sentient）"
        # 交易对格式
        r'\b([A-Z]{2,10})[/\-](USD|USDT|BTC|ETH|EUR|GBP|KRW|USDC)',  # "IRYSUSDT" 或 "AERO/USDC"
        # Alpha Coin 格式（优先匹配，因为更具体）
        r'new\s+binance\s+alpha\s+coin[:\s]+([A-Z]{2,10})',  # "New Binance Alpha Coin: VSN"
        r'binance\s+alpha\s+coin[:\s]+([A-Z]{2,10})',  # "Binance Alpha Coin: VSN"
        r'alpha\s+coin[:\s]+([A-Z]{2,10})',  # "Alpha Coin: VSN"
        # 韩文格式
        r'([A-Z]{2,10})\s*\([^)]+\)\s*원화',  # "아이리스(IRYS) 원화"
        r'플룸\s*\(([A-Z]{2,10})\)',  # "플룸(PLUME)"
        r'([A-Z]{2,10})\s+KRW',  # "PLUME KRW"
        # 标准 listing 格式
        r'list\s+([A-Z]{2,10})\s+for',  # "list DASH for"
        r'list\s+([A-Z]{2,10})',  # "list DASH"
        r'listing\s+of\s+([A-Z]{2,10})',  # "listing of BTC"
        r'to\s+list\s+([A-Z]{2,10})',  # "to list TRUTH"
        r'上线\s+([A-Z]{2,10})',  # "上线 SEI"
        r'add\s+([A-Z]{2,10})',  # "add BTC"
        # 其他格式
        r'\$([A-Z]{2,10})\b',  # $BTC 格式
        r'\b([A-Z]{3,10})\s+(?:will|to|is|are|has|have|listing|list|on|for)',  # 代币名称后跟 listing 相关词
        r'introducing\s+([A-Z]{2,10})',  # "Introducing APRO"
        r'\(([A-Z]{2,10})\)',  # "(IRYS)" 或 "(PLUME)"
        r'([A-Z]{2,10})\s*\(',  # "IRYS (" 或 "PLUME ("
        # 从交易对中提取，如 "IRYSUSDT" -> "IRYS"
        r'([A-Z]{2,10})(?:USDT|USD|BTC|ETH|EUR|GBP|KRW|USDC)',  # "IRYSUSDT" -> "IRYS"
    ]
    
    tokens = []
    token_display = {}  # 存储代币的显示名称，如 {"RLS": "Rayls (RLS)"}
    bracket_tokens = {}  # 存储括号内的代币，如 {"BOBBOB": "BOB"}
    
    # 先提取带括号的格式，支持两种格式：
    # 1. "Name (TOKEN)" - 如 "Rayls (RLS)" 或 "BOB (BOBBOB)"
    # 2. "TOKEN (Name)" - 如 "SENT (Sentient)"
    bracket_pattern1 = r'([A-Z][A-Za-z]+)\s*\(([A-Z]{2,10})\)'  # Name (TOKEN)
    bracket_pattern2 = r'([A-Z]{2,10})\s*\(([A-Z][A-Za-z]+)\)'  # TOKEN (Name)
    bracket_matches1 = re.findall(bracket_pattern1, text)
    bracket_matches2 = re.findall(bracket_pattern2, text)
    
    # 记录已处理的代币，避免重复
    processed_tokens = set()
    
    for display_name, token in bracket_matches1:
        token_upper = token.upper()
        if token_upper not in processed_tokens:
            bracket_tokens[token_upper] = display_name
            token_display[token_upper] = f"{display_name} ({token})"
            tokens.append(token_upper)
            processed_tokens.add(token_upper)
    
    for token, display_name in bracket_matches2:
        token_upper = token.upper()
        if token_upper not in processed_tokens:
            token_display[token_upper] = f"{token} ({display_name})"  # 修正：应该是 "SENT (Sentient)" 而不是 "Sentient (SENT)"
            tokens.append(token_upper)
            processed_tokens.add(token_upper)
    
    # 然后提取其他格式的代币
    for pattern in token_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                # 处理带括号的格式（已经在上面处理过了，跳过）
                if len(match) == 2:
                    token1, token2 = match
                    token1_upper = token1.upper()
                    token2_upper = token2.upper()
                    # 检查是否已经处理过（避免重复）
                    # 如果第一个是大写字母（可能是 TOKEN (Name) 格式），检查是否已处理
                    if len(token1) >= 2 and token1.isupper() and len(token2) >= 2 and not token2.isupper():
                        if token1_upper in processed_tokens:
                            continue
                    # 如果第二个是大写字母（可能是 Name (TOKEN) 格式），检查是否已处理
                    elif len(token2) >= 2 and token2.isupper() and len(token1) >= 2 and not token1.isupper():
                        if token2_upper in processed_tokens:
                            continue
                    # 其他情况，跳过所有带括号的格式（已经在上面处理过了）
                    continue
                else:
                    token = match[0]
            else:
                token = match
            
            # 过滤掉常见单词和交易所名称
            exchange_names = ['BINANCE', 'COINBASE', 'OKX', 'OKEX', 'KRAKEN', 'BYBIT', 'HUOBI', 'KUCOIN', 
                            'BITFINEX', 'BITSTAMP', 'GATE', 'BITHUMB', 'UPBIT', 'MEXC', 'BITGET', 'BITMART',
                            'HYPERLIQUID', 'USD', 'USDT', 'USDC', 'KRW', 'BTC', 'ETH', 'EUR', 'GBP']
            
            token_upper = token.upper()
            # 如果这个代币已经在括号中出现过（如 BOB 在 "BOB (BOBBOB)" 中），跳过
            if token_upper in bracket_tokens.values():
                continue
            # 如果已经处理过，跳过
            if token_upper in processed_tokens:
                continue
            if token_upper not in exclude_tokens and token_upper not in exchange_names:
                if len(token) >= 2 and token_upper not in tokens:
                    tokens.append(token_upper)
    
    # 如果从交易对中提取（如 IRYSUSDT），需要清理
    cleaned_tokens = []
    for token in tokens:
        # 移除交易对后缀
        for suffix in ['USDT', 'USD', 'USDC', 'BTC', 'ETH', 'EUR', 'GBP', 'KRW']:
            if token.endswith(suffix) and len(token) > len(suffix):
                token = token[:-len(suffix)]
                break
        # 如果这个代币是括号内代币的显示名称（如 BOB 是 BOBBOB 的显示名称），跳过
        if token in bracket_tokens.values():
            continue
        if token not in cleaned_tokens:
            cleaned_tokens.append(token)
    tokens = cleaned_tokens
    
    # 提取时间
    time_pattern = r'(\d{1,2}):(\d{2})\s*(?:AM|PM|am|pm)?\s*(UTC|utc|GMT|gmt)?'
    time_match = re.search(time_pattern, text)
    
    # 提取交易对
    pairs_pattern = r'([A-Z]{2,10})[/\-](USD|USDT|BTC|ETH|EUR|GBP)'
    pairs = re.findall(pairs_pattern, text)
    
    # 如果找到代币和交易所，创建 listing 对象
    if tokens and exchanges:
        # 处理日期
        listing_date = None
        if date_match:
            try:
                groups = date_match.groups()
                if len(groups) == 3:
                    # 月份名称映射
                    month_names = {
                        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    
                    # 判断日期格式
                    # 先检查是否是中文日期格式（2025年10月23日）
                    if '年' in text or '月' in text or '日' in text:
                        # 检查是否是中文日期格式
                        chinese_pattern = r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日'
                        chinese_match = re.search(chinese_pattern, text)
                        if chinese_match:
                            year, month, day = chinese_match.groups()
                            year = int(year)
                            month = int(month)
                            day = int(day)
                        elif len(groups[0]) == 4:  # YYYY-MM-DD
                            year, month, day = groups
                            year = int(year)
                            month = int(month)
                            day = int(day)
                        else:
                            # 其他格式
                            year, month, day = groups
                            year = int(year)
                            month = int(month)
                            day = int(day)
                    elif len(groups[0]) == 4:  # YYYY-MM-DD
                        year, month, day = groups
                        year = int(year)
                        month = int(month)
                        day = int(day)
                    elif len(groups[2]) == 4:  # MM-DD-YYYY 或 英文月份格式
                        # 检查是否是英文月份格式
                        if groups[0].lower() in month_names:  # Oct 23, 2025
                            month_name, day, year = groups
                            year = int(year)
                            month = month_names[month_name.lower()]
                            day = int(day)
                        elif groups[1].lower() in month_names:  # 23 Oct 2025
                            day, month_name, year = groups
                            year = int(year)
                            month = month_names[month_name.lower()]
                            day = int(day)
                        else:  # MM-DD-YYYY
                            month, day, year = groups
                            year = int(year)
                            month = int(month)
                            day = int(day)
                    else:
                        # 可能是其他格式，尝试解析
                        year, month, day = groups
                        year = int(year)
                        month = int(month)
                        day = int(day)
                    
                    # 验证日期有效性
                    if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                        listing_date = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
            except (ValueError, IndexError, KeyError):
                pass
        
        # 如果没有从消息文本中提取到日期
        # 对于 Alpha Coin，可以使用消息发布日期（因为 Alpha Coin 通常是即时上线的）
        # 对于其他类型，如果没有日期则跳过（因为消息发布日期可能不是上币日期）
        if not listing_date:
            if 'alpha' in listing_types:
                if message_date:
                    # Alpha Coin 使用消息发布日期
                    listing_date = message_date
                else:
                    # Alpha Coin 但没有消息发布日期，跳过
                    return []
            else:
                # 非 Alpha Coin 必须有日期
                return []
        
        # 处理时间
        listing_time = None
        if time_match:
            listing_time = f"{time_match.group(1)}:{time_match.group(2)}"
            if time_match.group(3):
                listing_time += f" {time_match.group(3).upper()}"
        
        # 处理交易对
        listing_pairs = None
        if pairs:
            listing_pairs = '/'.join(pairs[0]) if pairs else None
        
        # 为每个代币和交易所组合创建 listing
        # 先统一交易所名称为英文（在创建 listing 时就转换，避免重复）
        exchange_name_map = {
            '币安': 'Binance',
            '欧易': 'OKX',
            '火币': 'Huobi',
            'gate': 'Gate',
            '库币': 'KuCoin',
        }
        
        for token in tokens[:5]:  # 最多取前5个代币
            for exchange in list(set(exchanges))[:2]:  # 去重，最多取前2个交易所
                # 统一交易所名称为英文
                exchange_normalized = exchange_name_map.get(exchange, exchange).title()
                
                # 使用显示名称（如果有），否则使用代币代码
                display_token = token_display.get(token, token)
                
                # 为每个类型创建 listing（如果一条消息包含多个类型）
                for listing_type in listing_types:
                    listing = {
                        'date': listing_date,
                        'token': token,  # 代币代码
                        'token_display': display_token,  # 显示名称，如 "Rayls (RLS)"
                        'exchange': exchange_normalized,  # 已转换为英文
                        'type': listing_type,  # perp, spot 或 alpha
                        'text': text[:300]  # 保存原始文本的前300字符
                    }
                    
                    if listing_time:
                        listing['time'] = listing_time
                    if pairs:
                        # 找到匹配的交易对
                        for pair in pairs:
                            if pair[0].upper() == token.upper():
                                listing['pairs'] = f"{pair[0]}/{pair[1]}"
                                break
                    
                    listings.append(listing)
    
    return listings


async def scrape_channel():
    """爬取频道消息"""
    print(f"正在连接 Telegram...")
    
    # 创建客户端
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    
    try:
        # 检查是否已有会话
        if Path(SESSION_FILE).exists():
            print("发现已有会话文件，尝试使用...")
        
        # 尝试连接，如果会话有效则不需要输入
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            print("\n⚠️  会话已过期，需要重新登录。")
            print("\n开始登录流程...")
            print("=" * 50)
            
            # 重新连接以进行登录
            await client.connect()
            
            # 获取手机号
            try:
                phone = input("\n请输入你的手机号（带国家代码，如 +86138xxxxxxxx）: ")
                print(f"\n正在向 {phone} 发送验证码...")
                await client.send_code_request(phone)
                print("✓ 验证码已发送！")
                
                # 获取验证码
                code = input("\n请输入收到的验证码: ")
                
                try:
                    await client.sign_in(phone, code)
                    print("✓ 登录成功！")
                except SessionPasswordNeededError:
                    print("\n检测到两步验证...")
                    password = input("请输入两步验证密码: ")
                    await client.sign_in(password=password)
                    print("✓ 登录成功！")
                    
            except (EOFError, KeyboardInterrupt):
                print("\n\n❌ 登录被取消。")
                await client.disconnect()
                return []
            except Exception as e:
                print(f"\n❌ 登录失败: {e}")
                await client.disconnect()
                return []
        
        print("✓ 连接成功！")
        
        print(f"\n正在获取频道 @{CHANNEL_USERNAME} 的消息...")
        
        # 获取频道实体
        entity = await client.get_entity(CHANNEL_USERNAME)
        print(f"频道名称: {entity.title}")
        print(f"频道ID: {entity.id}\n")
        
        # 获取消息
        all_listings = []
        message_count = 0
        
        async for message in client.iter_messages(entity, limit=MESSAGE_LIMIT):
            message_count += 1
            if message.text:
                # 获取消息发布日期，用于 Alpha Coin 等没有明确日期的消息
                msg_date = message.date.strftime('%Y-%m-%d')
                listings = extract_listing_info(message.text, message_date=msg_date)
                if listings:
                    # 添加消息日期作为参考
                    for listing in listings:
                        # 确保日期有效（extract_listing_info 已经确保日期存在）
                        date = listing.get('date', '')
                        if not date or len(date) != 10 or date.count('-') != 2:
                            # 如果日期无效，跳过这条 listing（不应该发生，因为 extract_listing_info 已经检查过）
                            print(f"⚠️ 警告：消息 #{message.id} 的 listing 日期无效: {date}，跳过")
                            continue
                        listing['message_id'] = message.id
                        listing['message_date'] = msg_date
                        all_listings.append(listing)
                    if listings:
                        print(f"✓ 找到 {len([l for l in listings if l.get('date')])} 个 listing (消息 #{message.id})")
        
        print(f"\n总共处理了 {message_count} 条消息")
        print(f"找到 {len(all_listings)} 个 CEX listing 信息\n")
        
        # 去重（基于日期、代币、交易所和类型）
        # 先统一交易所名称为英文（避免中英文重复）
        exchange_name_map = {
            '币安': 'Binance',
            '欧易': 'OKX',
            '火币': 'Huobi',
            'Gate': 'Gate',
            '库币': 'KuCoin',
        }
        
        for listing in all_listings:
            exchange = listing.get('exchange', '')
            if exchange in exchange_name_map:
                listing['exchange'] = exchange_name_map[exchange]
        
        # 代币名称规范化（处理 BOBBOB/BOB 这种情况）
        def normalize_token(token, token_display):
            """规范化代币名称，处理变体"""
            token_upper = token.upper()
            # 如果代币显示名称包含括号，优先使用括号内的代码
            if token_display and '(' in token_display:
                # 提取括号内的代码，如 "BOB (BOBBOB)" -> "BOBBOB"
                import re
                match = re.search(r'\(([A-Z0-9]+)\)', token_display)
                if match:
                    return match.group(1).upper()
            return token_upper
        
        # 处理重复的代币（如 BOB 和 BOBBOB）
        # 如果两个代币中一个是另一个的子串，且较长的在 token_display 的括号中，使用较长的
        token_groups = {}
        for listing in all_listings:
            token = listing.get('token', '').upper()
            token_display = listing.get('token_display', token)
            normalized = normalize_token(token, token_display)
            
            # 如果规范化后的代币与原始不同，更新
            if normalized != token:
                listing['token'] = normalized
                if token_display and '(' in token_display:
                    import re
                    # 更新显示名称，确保括号内是规范化后的代码
                    token_display = re.sub(r'\([^)]+\)', f'({normalized})', token_display)
                    listing['token_display'] = token_display
        
        # 去重（先规范化所有代币）
        for listing in all_listings:
            token = listing.get('token', '').upper()
            token_display = listing.get('token_display', token)
            normalized_token = normalize_token(token, token_display)
            
            # 如果规范化后的代币与原始不同，更新
            if normalized_token != token:
                listing['token'] = normalized_token
                if token_display and '(' in token_display:
                    import re
                    # 更新显示名称，确保括号内是规范化后的代码
                    token_display = re.sub(r'\([^)]+\)', f'({normalized_token})', token_display)
                    listing['token_display'] = token_display
                elif token_display and token_display != token:
                    # 如果 token_display 是 "BOB" 但 token 应该是 "BOBBOB"，更新显示名称
                    # 这种情况需要从原始文本中查找
                    pass
        
        # 去重
        unique_listings = []
        seen = set()
        for listing in all_listings:
            # 确保日期格式正确
            date = listing.get('date', '')
            if date and len(date) == 10 and date.count('-') == 2:
                # 统一交易所名称为小写进行比较
                exchange_lower = listing['exchange'].lower()
                token = listing.get('token', '').upper()
                key = (date, token, exchange_lower, listing.get('type', 'spot'))
                if key not in seen:
                    seen.add(key)
                    unique_listings.append(listing)
        
        print(f"去重后剩余 {len(unique_listings)} 个 listing\n")
        
        # 按日期排序
        unique_listings.sort(key=lambda x: x['date'])
        
        # 保存为 JSON
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(unique_listings, f, ensure_ascii=False, indent=2)
        print(f"✓ 已保存到 {OUTPUT_JSON}")
        
        # 更新 data.js
        update_data_js(unique_listings)
        print(f"✓ 已更新 {OUTPUT_JS}")
        
        return unique_listings
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


def update_data_js(listings):
    """更新 data.js 文件"""
    js_content = "// CEX Listing 数据\n"
    js_content += "// 格式：{ date: 'YYYY-MM-DD', token: '代币代码', token_display: '显示名称', exchange: '交易所', type: 'perp/spot/alpha', time: '时间', pairs: '交易对', notes: '备注' }\n"
    js_content += "// 自动从 @news6551 爬取的数据\n\n"
    js_content += "const cexListings = [\n"
    
    for listing in listings:
        js_content += "    {\n"
        js_content += f"        date: '{listing['date']}',\n"
        js_content += f"        token: '{listing['token']}',\n"
        # 使用显示名称（如果有），否则使用代币代码
        token_display = listing.get('token_display', listing['token'])
        js_content += f"        token_display: '{token_display}',\n"
        js_content += f"        exchange: '{listing['exchange']}',\n"
        js_content += f"        type: '{listing.get('type', 'spot')}',\n"
        if listing.get('time'):
            js_content += f"        time: '{listing['time']}',\n"
        if listing.get('pairs'):
            js_content += f"        pairs: '{listing['pairs']}',\n"
        if listing.get('text'):
            # 清理文本，移除换行和引号
            text = listing['text'].replace('\n', ' ').replace("'", "\\'").replace('"', '\\"')
            js_content += f"        notes: '{text[:150]}',\n"
        js_content += "    },\n"
    
    js_content += "];\n"
    
    with open(OUTPUT_JS, 'w', encoding='utf-8') as f:
        f.write(js_content)


if __name__ == '__main__':
    print("=" * 50)
    print("Telegram Channel Scraper - @news6551")
    print("=" * 50)
    print()
    
    # 检查配置
    if API_ID == 'YOUR_API_ID' or API_HASH == 'YOUR_API_HASH':
        print("⚠️  请先配置 API_ID 和 API_HASH！")
        print()
        print("方法1：创建配置文件（推荐）")
        print("  1. 复制 config.example.py 为 config.py")
        print("  2. 编辑 config.py，填入你的 API_ID 和 API_HASH")
        print()
        print("方法2：直接编辑 scraper.py")
        print("  在文件开头修改 API_ID 和 API_HASH 的值")
        print()
        print("获取 API 凭证：")
        print("  1. 访问 https://my.telegram.org/apps")
        print("  2. 登录你的 Telegram 账号")
        print("  3. 创建应用，获取 api_id 和 api_hash")
        print()
        exit(1)
    
    # 运行爬虫
    asyncio.run(scrape_channel())
    
    print()
    print("=" * 50)
    print("完成！")
    print("=" * 50)

