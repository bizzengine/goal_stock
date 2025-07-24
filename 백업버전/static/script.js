// 전역 변수로 종목 데이터 저장
let tickerData = [];

// 페이지 로드 시 tickers.json 파일을 불러옴
async function loadTickerData() {
    try {
        const response = await fetch('/autocomplete');
        if (response.ok) {
            tickerData = await response.json();
            console.log(`${tickerData.length}개의 종목 데이터를 로드했습니다.`);
        } else {
            console.warn('tickers.json 파일을 찾을 수 없습니다. 자동완성 기능이 비활성화됩니다.');
        }
    } catch (error) {
        console.warn('tickers.json 로드 중 오류:', error);
    }
}

// 자동완성 기능
function setupAutocomplete(input) {
    const container = input.parentElement;
    container.classList.add('autocomplete-container');

    let dropdown = container.querySelector('.autocomplete-dropdown');
    let activeIndex = -1;

    input.addEventListener('input', function () {
        const value = this.value.toUpperCase().trim();

        // 기존 dropdown 제거
        if (dropdown) {
            dropdown.remove();
        }

        if (value.length === 0) {
            return;
        }

        // 검색 결과 필터링 (심볼로만 검색)
        const filtered = tickerData.filter(ticker =>
            ticker.symbol.toUpperCase().includes(value)
        ).slice(0, 10); // 최대 10개만 표시

        if (filtered.length === 0) {
            return;
        }

        // dropdown 생성
        dropdown = document.createElement('div');
        dropdown.className = 'autocomplete-dropdown';

        filtered.forEach((ticker, index) => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.innerHTML = `
                <span class="autocomplete-symbol">${ticker.symbol}</span>
                <span class="autocomplete-name">${ticker.name}</span>
                <span class="autocomplete-rank">Rank ${ticker.rank}</span>
            `;

            item.addEventListener('click', function () {
                input.value = ticker.symbol;
                dropdown.remove();
                activeIndex = -1;
            });

            dropdown.appendChild(item);
        });

        container.appendChild(dropdown);
        activeIndex = -1;
    });

    // 키보드 네비게이션
    input.addEventListener('keydown', function (e) {
        if (!dropdown) return;

        const items = dropdown.querySelectorAll('.autocomplete-item');

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeIndex = activeIndex < items.length - 1 ? activeIndex + 1 : 0;
            updateActiveItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeIndex = activeIndex > 0 ? activeIndex - 1 : items.length - 1;
            updateActiveItem(items);
        } else if (e.key === 'Enter' && activeIndex >= 0) {
            e.preventDefault();
            items[activeIndex].click();
        } else if (e.key === 'Escape') {
            dropdown.remove();
            activeIndex = -1;
        }
    });

    // 외부 클릭시 dropdown 닫기
    document.addEventListener('click', function (e) {
        if (!container.contains(e.target) && dropdown) {
            dropdown.remove();
            activeIndex = -1;
        }
    });
}

function updateActiveItem(items) {
    items.forEach((item, index) => {
        if (index === activeIndex) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

function addStockRow(ticker = "", date = "") {
    const row = document.createElement("div");
    row.className = "row mb-2 align-items-center stock-row";
    row.innerHTML = `
        <div class="col-5">
            <input type="text" name="tickers" class="form-control form-control-sm ticker-input" placeholder="예: AAPL" value="${ticker}" required />
        </div>
        <div class="col-5">
            <input type="text" name="buy_dates" class="form-control form-control-sm flatpickr-input" placeholder="매수일 선택" value="${date}" required />
        </div>
        <div class="col-2 text-end">
            <button type="button" class="btn btn-outline-danger btn-sm" onclick="this.closest('.stock-row').remove()">-</button>
        </div>
    `;
    const stockList = document.getElementById("stock-list");
    stockList.appendChild(row);

    // 새로 추가된 ticker input에 자동완성 설정
    const tickerInput = row.querySelector(".ticker-input");
    if (tickerData.length > 0) {
        setupAutocomplete(tickerInput);
    }

    // 새로 추가된 input 필드에 Flatpickr 초기화
    flatpickr(row.querySelector(".flatpickr-input"), {
        dateFormat: "Y-m-d",
        locale: "ko",
        enableTime: false,
        allowInput: true
    });
}

// 폼 제출 처리
document.querySelector('form').addEventListener('submit', async function (e) {
    e.preventDefault();

    // 분석 시작할 때마다 이전 에러/결과 영역 숨기기
    document.getElementById('error-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'none';
    document.getElementById('realized-table').style.display = 'none';
    document.getElementById('unrealized-table').style.display = 'none';

    const formData = new FormData(this);

    try {
        const response = await fetch('/', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (result.error) {
            showError(result.error);
        } else {
            showResult(result);
        }
    } catch (error) {
        showError('서버와 통신 중 오류가 발생했습니다.');
        console.error('Error:', error);
    }
});

function showError(message) {
    // 에러 보이기
    document.getElementById('error-message').textContent = message;
    document.getElementById('error-section').style.display = 'block';
    // 결과 섹션 완전 숨기기
    document.getElementById('result-section').style.display = 'none';
    // 테이블도 숨김
    document.getElementById('realized-table').style.display = 'none';
    document.getElementById('unrealized-table').style.display = 'none';
}

function showResult(data) {
    // (다시) 결과 섹션 보이기 전에 이전 테이블 숨기기
    document.getElementById('realized-table').style.display = 'none';
    document.getElementById('unrealized-table').style.display = 'none';

    document.getElementById('error-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'block';

    // 요약 정보 업데이트
    document.getElementById('overall-avg').textContent = data.overall_avg_profit + '%';
    document.getElementById('realized-count').textContent = data.realized_count + '개';
    document.getElementById('unrealized-count').textContent = data.unrealized_count + '개';
    document.getElementById('avg-days').textContent = data.avg_realized_days + '일';

    // 실현된 종목 테이블
    const realizedTable = document.getElementById('realized-table');
    const realizedTbody = document.getElementById('realized-tbody');
    realizedTbody.innerHTML = '';
    if (data.realized_list && data.realized_list.length > 0) {
        realizedTable.style.display = 'block';
        data.realized_list.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${row.symbol}</strong></td>
                <td>${row.buy_date}</td>
                <td>$${row.buy_price.toFixed(2)}</td>
                <td>$${row.sell_price.toFixed(2)}</td>
                <td>${row.achieve_date}</td>
                <td><span class="badge bg-success">${row.profit}%</span></td>
                <td>${row.days}일</td>
            `;
            realizedTbody.appendChild(tr);
        });
    }

    // 미실현 종목 테이블
    const unrealTable = document.getElementById('unrealized-table');
    const unrealTbody = document.getElementById('unrealized-tbody');
    unrealTbody.innerHTML = '';
    if (data.unrealized_list && data.unrealized_list.length > 0) {
        unrealTable.style.display = 'block';
        data.unrealized_list.forEach(row => {
            const tr = document.createElement('tr');
            const badgeClass = row.profit > 0 ? 'bg-success' : 'bg-danger';
            tr.innerHTML = `
                <td><strong>${row.symbol}</strong></td>
                <td>${row.buy_date}</td>
                <td>$${row.buy_price.toFixed(2)}</td>
                <td>$${row.sell_price.toFixed(2)}</td>
                <td><span class="badge ${badgeClass}">${row.profit}%</span></td>
                <td>${row.days}일</td>
            `;
            unrealTbody.appendChild(tr);
        });
    }
}

// Flatpickr 한국어 로케일 추가 (선택 사항)
if (flatpickr.l10ns) {
    flatpickr.l10ns.ko = {
        weekdays: {
            shorthand: ["일", "월", "화", "수", "목", "금", "토"],
            longhand: ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"],
        },
        months: {
            shorthand: ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"],
            longhand: ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"],
        },
        rangeSeparator: " ~ ",
        firstDayOfWeek: 0,
        ordinal: function () {
            return "";
        },
    };
}

// 페이지 로드 시 실행
window.onload = async function () {
    // 종목 데이터 로드
    await loadTickerData();
    // 기본 종목 입력 행 추가
    addStockRow();
};