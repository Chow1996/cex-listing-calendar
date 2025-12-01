# 📤 GitHub 上传说明

## ✅ 文件夹已准备好

这个文件夹包含了所有需要上传到 GitHub 的文件。

## ⚠️ 重要：还需要添加一个文件

**请手动将桌面上的 `cexscraper.py` 复制到这个文件夹，并重命名为 `scraper.py`**

或者上传到 GitHub 后，在网页上重命名也可以。

---

## 📋 当前文件夹内容

✅ index.html
✅ style.css  
✅ script.js
✅ data.js
✅ config.example.py
✅ requirements.txt
✅ vercel.json
✅ .gitignore
✅ README.md
✅ 快速上手.md
✅ 上传清单.md

**还需要添加：**
- ⚠️ scraper.py (从桌面的 cexscraper.py 复制并重命名)

---

## 🚀 上传步骤

1. **添加 scraper.py**
   - 将桌面的 `cexscraper.py` 复制到这个文件夹
   - 重命名为 `scraper.py`

2. **在 GitHub 创建仓库**
   - 仓库名：`cex-listing-calendar`
   - 不要初始化 README

3. **上传所有文件**
   - 点击 "uploading an existing file"
   - 上传这个文件夹里的所有文件
   - **注意**：`.gitignore` 是隐藏文件，Mac 按 `Cmd + Shift + .` 显示

4. **提交**
   - Commit message: `Initial commit`
   - 点击 "Commit changes"

---

## 📝 上传后的操作

### 部署到 Vercel
1. 访问 vercel.com
2. 导入 GitHub 仓库
3. 自动部署

### 本地连接仓库（可选）
```bash
git clone https://github.com/yourusername/cex-listing-calendar.git
cd cex-listing-calendar
```

---

## ⚠️ 不要上传

- `config.py` (包含 API 密钥)
- `telegram_session.session`
- `cex_listings.json` (可选)

