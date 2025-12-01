// 当前显示的月份和年份
let currentDate = new Date();
let currentMonth = currentDate.getMonth();
let currentYear = currentDate.getFullYear();

// 月份名称
const monthNames = [
    '一月', '二月', '三月', '四月', '五月', '六月',
    '七月', '八月', '九月', '十月', '十一月', '十二月'
];

// 初始化日历
function initCalendar() {
    updateCalendarHeader();
    renderCalendar();
    setupEventListeners();
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
    return cexListings.filter(event => event.date === dateStr);
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
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', initCalendar);

