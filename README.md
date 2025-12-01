# CEX Listing 日历

一个展示 CEX（中心化交易所）上市信息的日历网页，数据来自 Telegram 频道 @news6551。

## 功能特点

- 📅 日历视图展示所有上市信息
- 🎨 不同交易所使用不同颜色区分
- 📊 支持 Spot、Perp、Pre-Market 等类型
- 📱 响应式设计，支持移动端
- 🔄 自动更新数据

## 文件说明

- `index.html` - 主页面
- `style.css` - 样式文件
- `script.js` - JavaScript 逻辑
- `data.js` - 数据文件（由爬虫自动生成）
- `scraper.py` - 爬虫程序

## 部署

### Vercel 部署

1. Fork 或克隆此仓库
2. 在 [Vercel](https://vercel.com) 导入项目
3. 自动部署完成

### 本地运行

```bash
# 使用 Python 简单服务器
python3 -m http.server 8000

# 或使用 Node.js
npx serve
```

然后访问 http://localhost:8000

## 数据更新

数据通过 `scraper.py` 从 Telegram 频道爬取，需要：
1. Telegram API 凭证（API_ID, API_HASH）
2. 运行爬虫更新 `data.js`

详细说明请查看 `README_DEPLOY.md`

## 许可证

MIT License
