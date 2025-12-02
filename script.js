// 当前显示的月份和年份
let currentDate = new Date();
let currentMonth = currentDate.getMonth();
let currentYear = currentDate.getFullYear();

// 当前筛选的交易所（空字符串表示不过滤）
let selectedExchange = '';

// 月份名称
const monthNames = [
    '一月', '二月', '三月', '四月', '五月', '六月',
    '七月', '八月', '九月', '十月', '十一月', '十二月'
];

// 初始化日历
function initCalendar() {
    initExchangeFilter();
    updateCalendarHeader();
    renderCalendar();
    updateExchangeStats();
    setupEventListeners();
}

// 初始化交易所筛选下拉框
function initExchangeFilter() {
    const filter = document.getElementById('exchangeFilter');
    
    // 获取所有唯一的交易所
    const exchanges = [...new Set(cexListings.map(event => event.exchange).filter(Boolean))].sort();
    
    // 添加选项
    exchanges.forEach(exchange => {
        const option = document.createElement('option');
        option.value = exchange;
        option.textContent = exchange;
        filter.appendChild(option);
    });
}

// 更新日历标题
function updateCalendarHeader() {
    const header = document.getElementById('currentMonth');
    header.textContent = `${currentYear}年 ${monthNames[currentMonth]}`;
}

// 渲染日历
function renderCalendar() {
    const calendar = document.getElementById('calendar');
    calendar.innerHTML = '';

    // 获取当月第一天是星期几（0=周日, 6=周六）
    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    // 获取当月有多少天
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    // 获取上个月有多少天
    const daysInPrevMonth = new Date(currentYear, currentMonth, 0).getDate();

    // 填充上个月的日期
    for (let i = firstDay - 1; i >= 0; i--) {
        const day = daysInPrevMonth - i;
        const dateStr = formatDate(currentYear, currentMonth - 1, day);
        calendar.appendChild(createDayElement(day, dateStr, true));
    }

    // 填充当月的日期
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = formatDate(currentYear, currentMonth, day);
        calendar.appendChild(createDayElement(day, dateStr, false));
    }

    // 填充下个月的日期（填满6行）
    const totalCells = calendar.children.length;
    const remainingCells = 42 - totalCells; // 6行 x 7列 = 42
    for (let day = 1; day <= remainingCells; day++) {
        const dateStr = formatDate(currentYear, currentMonth + 1, day);
        calendar.appendChild(createDayElement(day, dateStr, true));
    }
}

// 创建日期元素
function createDayElement(day, dateStr, isOtherMonth) {
    const dayElement = document.createElement('div');
    dayElement.className = 'calendar-day';
    
    if (isOtherMonth) {
        dayElement.classList.add('other-month');
    }

    // 检查是否是今天
    const today = new Date();
    if (!isOtherMonth && 
        day === today.getDate() && 
        currentMonth === today.getMonth() && 
        currentYear === today.getFullYear()) {
        dayElement.classList.add('today');
    }

    // 检查该日期是否有事件
    const events = getEventsForDate(dateStr);
    if (events.length > 0) {
        dayElement.classList.add('has-events');
        
        // 添加事件数量标记
        const countBadge = document.createElement('div');
        countBadge.className = 'event-count';
        countBadge.textContent = events.length;
        dayElement.appendChild(countBadge);
    }

    // 添加日期数字
    const dayNumber = document.createElement('div');
    dayNumber.className = 'day-number';
    dayNumber.textContent = day;
    dayElement.appendChild(dayNumber);

    // 添加所有事件预览（不限制数量）
    events.forEach(event => {
        const eventItem = document.createElement('div');
        eventItem.className = 'event-item';
        const type = event.type || 'spot';
        const typeLabel = type === 'perp' ? 'Perp' : (type === 'alpha' ? 'Alpha' : (type === 'pre-market' ? 'Pre-Market' : 'Spot'));
        const typeClass = type === 'perp' ? 'event-perp' : (type === 'alpha' ? 'event-alpha' : (type === 'pre-market' ? 'event-premarket' : 'event-spot'));
        const exchange = event.exchange || 'Unknown';
        const exchangeClass = getExchangeClass(exchange);
        // 使用显示名称（如果有），否则使用代币代码
        const tokenDisplay = event.token_display || event.token || 'Unknown';
        eventItem.className = `event-item ${typeClass} ${exchangeClass}`;
        // 显示格式：交易所-类型-代币（按用户要求的顺序）
        eventItem.textContent = `${exchange}-${typeLabel}-${tokenDisplay}`;
        eventItem.title = `${exchange}-${typeLabel}-${tokenDisplay}`;
        dayElement.appendChild(eventItem);
    });

    // 点击日期显示详情
    dayElement.addEventListener('click', () => {
        showEventModal(dateStr, events);
    });

    return dayElement;
}

// 格式化日期为 YYYY-MM-DD
function formatDate(year, month, day) {
    const m = month + 1; // 月份从0开始，所以要+1
    return `${year}-${String(m).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

// 获取交易所对应的 CSS 类名
function getExchangeClass(exchange) {
    const exchangeLower = (exchange || '').toLowerCase();
    const exchangeMap = {
        'binance': 'exchange-binance',
        '币安': 'exchange-binance',
        'coinbase': 'exchange-coinbase',
        'bybit': 'exchange-bybit',
        'okx': 'exchange-okx',
        'okex': 'exchange-okx',
        'upbit': 'exchange-upbit',
        'bithumb': 'exchange-bithumb',
        'kraken': 'exchange-kraken',
        'huobi': 'exchange-huobi',
        'gate.io': 'exchange-gate',
        'gateio': 'exchange-gate',
        'gate': 'exchange-gate',
        'kucoin': 'exchange-kucoin',
        'mexc': 'exchange-mexc',
        'bitget': 'exchange-bitget',
        'bitmart': 'exchange-bitmart',
        'hyperliquid': 'exchange-hyperliquid',
    };
    return exchangeMap[exchangeLower] || 'exchange-default';
}

// 获取指定日期的事件
function getEventsForDate(dateStr) {
    let events = cexListings.filter(event => event.date === dateStr);
    
    // 如果选择了交易所筛选，则进一步过滤
    if (selectedExchange) {
        events = events.filter(event => event.exchange === selectedExchange);
    }
    
    return events;
}

// 显示事件详情模态框
function showEventModal(dateStr, events) {
    const modal = document.getElementById('eventModal');
    const modalDate = document.getElementById('modalDate');
    const modalEvents = document.getElementById('modalEvents');

    const date = new Date(dateStr);
    modalDate.textContent = `${date.getFullYear()}年 ${date.getMonth() + 1}月 ${date.getDate()}日`;

    if (events.length === 0) {
        modalEvents.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">该日期暂无上市信息</p>';
    } else {
        modalEvents.innerHTML = events.map(event => {
            const type = event.type || 'spot';
            const typeLabel = type === 'perp' ? 'Perp' : (type === 'alpha' ? 'Alpha' : (type === 'pre-market' ? 'Pre-Market' : 'Spot'));
            const typeClass = type === 'perp' ? 'type-perp' : (type === 'alpha' ? 'type-alpha' : (type === 'pre-market' ? 'type-premarket' : 'type-spot'));
            const tokenDisplay = event.token_display || event.token || '未知代币';
            return `
            <div class="event-detail">
                <div class="event-header">
                    <h3>${event.exchange || '未知'}-${typeLabel}-${tokenDisplay}</h3>
                    <span class="type-badge ${typeClass}">${typeLabel}</span>
                </div>
                ${event.time ? `<p><strong>时间：</strong>${event.time}</p>` : ''}
                ${event.pairs ? `<p><strong>交易对：</strong>${event.pairs}</p>` : ''}
                ${event.notes ? `<p class="event-notes"><strong>详情：</strong>${event.notes}</p>` : ''}
            </div>
        `;
        }).join('');
    }

    modal.style.display = 'block';
}

// 设置事件监听器
function setupEventListeners() {
    // 上个月按钮
    document.getElementById('prevMonth').addEventListener('click', () => {
        currentMonth--;
        if (currentMonth < 0) {
            currentMonth = 11;
            currentYear--;
        }
        updateCalendarHeader();
        renderCalendar();
        updateExchangeStats();
    });

    // 下个月按钮
    document.getElementById('nextMonth').addEventListener('click', () => {
        currentMonth++;
        if (currentMonth > 11) {
            currentMonth = 0;
            currentYear++;
        }
        updateCalendarHeader();
        renderCalendar();
        updateExchangeStats();
    });

    // 关闭模态框
    const modal = document.getElementById('eventModal');
    const closeBtn = document.querySelector('.close');
    
    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });

    // 交易所筛选
    const exchangeFilter = document.getElementById('exchangeFilter');
    exchangeFilter.addEventListener('change', (e) => {
        selectedExchange = e.target.value;
        renderCalendar();
        updateExchangeStats();
    });
}

// 更新交易所统计（只统计当前月份）
function updateExchangeStats() {
    const statsPanel = document.getElementById('exchangeStats');
    if (!statsPanel) return;
    
    // 获取当前月份的第一天和最后一天
    const firstDay = new Date(currentYear, currentMonth, 1);
    const lastDay = new Date(currentYear, currentMonth + 1, 0);
    const monthStart = formatDate(currentYear, currentMonth, 1);
    const monthEnd = formatDate(currentYear, currentMonth, lastDay.getDate());
    
    // 筛选当前月份的数据
    const monthEvents = cexListings.filter(event => {
        const eventDate = event.date;
        return eventDate >= monthStart && eventDate <= monthEnd;
    });
    
    // 获取所有交易所
    const exchanges = [...new Set(monthEvents.map(event => event.exchange).filter(Boolean))].sort();
    
    // 计算每个交易所的统计
    const stats = {};
    exchanges.forEach(exchange => {
        const exchangeEvents = monthEvents.filter(event => event.exchange === exchange);
        stats[exchange] = {
            total: exchangeEvents.length,
            spot: exchangeEvents.filter(e => e.type === 'spot').length,
            perp: exchangeEvents.filter(e => e.type === 'perp').length,
            premarket: exchangeEvents.filter(e => e.type === 'pre-market').length,
            alpha: exchangeEvents.filter(e => e.type === 'alpha').length
        };
    });
    
    // 按总数排序
    const sortedExchanges = exchanges.sort((a, b) => stats[b].total - stats[a].total);
    
    // 生成 HTML
    if (sortedExchanges.length === 0) {
        statsPanel.innerHTML = '<p style="color: #8a8fa3; text-align: center; padding: 20px;">该月暂无数据</p>';
        return;
    }
    
    statsPanel.innerHTML = sortedExchanges.map(exchange => {
        const stat = stats[exchange];
        return `
            <div class="exchange-stat-item">
                <div class="exchange-stat-header">
                    <span class="exchange-stat-name">${exchange}</span>
                    <span class="exchange-stat-total">${stat.total}</span>
                </div>
                <div class="exchange-stat-types">
                    ${stat.spot > 0 ? `<div class="stat-type-item spot">
                        <span class="stat-type-label">Spot</span>
                        <span class="stat-type-count">${stat.spot}</span>
                    </div>` : ''}
                    ${stat.perp > 0 ? `<div class="stat-type-item perp">
                        <span class="stat-type-label">Perp</span>
                        <span class="stat-type-count">${stat.perp}</span>
                    </div>` : ''}
                    ${stat.premarket > 0 ? `<div class="stat-type-item premarket">
                        <span class="stat-type-label">Pre-Market</span>
                        <span class="stat-type-count">${stat.premarket}</span>
                    </div>` : ''}
                    ${stat.alpha > 0 ? `<div class="stat-type-item alpha">
                        <span class="stat-type-label">Alpha</span>
                        <span class="stat-type-count">${stat.alpha}</span>
                    </div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', initCalendar);

