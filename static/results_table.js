document.addEventListener("DOMContentLoaded", () => {
    const table = document.getElementById("mainTable");
    const headers = table.querySelectorAll("th[data-sort-key]");
    const tbody = table.querySelector("tbody");

    // 행 클릭 이벤트 리스너 추가
    tbody.addEventListener("click", (event) => {
        const clickedRow = event.target.closest("tr");
        if (!clickedRow || clickedRow.classList.contains("error-row")) {
            return;
        }

        // 모든 행의 'selected-row' 클래스 제거
        tbody.querySelectorAll("tr").forEach((row) => {
            row.classList.remove("selected-row");
        });

        // 클릭된 행에 'selected-row' 클래스 추가
        clickedRow.classList.add("selected-row");
    });

    // 초기 상태: 비고, 에러 행, 구단주명 등 정렬에서 제외
    const initialOrder = Array.from(tbody.querySelectorAll("tr"))
        .filter((row) => !row.classList.contains("error-row"))
        .map((row) => (row.dataset.originalIndex = row.rowIndex));

    headers.forEach((header) => {
        header.addEventListener("click", () => {
            const sortKey = header.dataset.sortKey;
            const sortDirection = header.dataset.sortDirection === "desc" ? "asc" : "desc";

            // 모든 헤더의 정렬 상태 초기화
            headers.forEach((h) => {
                h.removeAttribute("data-sort-direction");
                h.classList.remove("sorted-asc", "sorted-desc");
            });

            // 현재 헤더에 정렬 상태 설정
            header.dataset.sortDirection = sortDirection;
            header.classList.add(`sorted-${sortDirection}`);

            sortTable(sortKey, sortDirection);
        });
    });

    function sortTable(sortKey, sortDirection) {
        const rows = Array.from(tbody.querySelectorAll("tr"));
        const errorRows = rows.filter((row) => row.classList.contains("error-row"));
        const dataRows = rows.filter((row) => !row.classList.contains("error-row"));

        const sortedRows = dataRows.sort((a, b) => {
            const aValue = getCellValue(a, sortKey);
            const bValue = getCellValue(b, sortKey);

            if (typeof aValue === "string") {
                return sortDirection === "asc" ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
            } else {
                return sortDirection === "asc" ? aValue - bValue : bValue - aValue;
            }
        });

        // 정렬된 행을 tbody에 다시 추가 (오류 행은 항상 마지막에)
        tbody.innerHTML = "";
        sortedRows.forEach((row) => tbody.appendChild(row));
        errorRows.forEach((row) => tbody.appendChild(row));
    }

    function getCellValue(row, key) {
        let value = null;
        switch (key) {
            case "순위":
            case "판수":
            case "채굴 효율":
                value = parseInt(row.querySelector(`td:nth-child(${getColumnIndex(key)})`).textContent.replace(/,/g, ""), 10);
                break;
            case "승률":
                value = parseFloat(row.querySelector(`td:nth-child(${getColumnIndex(key)})`).textContent.replace("%", ""));
                break;
            case "구단 가치":
                const text = row.querySelector(`td:nth-child(${getColumnIndex(key)})`).textContent;
                // 쉼표를 먼저 제거
                const cleanText = text.replace(/,/g, "");
                if (cleanText.includes("조")) {
                    value = parseFloat(cleanText.replace("조", "")) * 10000;
                } else if (cleanText.includes("억")) {
                    value = parseFloat(cleanText.replace("억", ""));
                }
                break;
            default:
                value = row.querySelector(`td:nth-child(${getColumnIndex(key)})`).textContent.trim();
        }
        return value;
    }

    function getColumnIndex(key) {
        const headers = Array.from(document.querySelectorAll("#mainTable th"));
        const header = headers.find((h) => h.dataset.sortKey === key);
        return header ? headers.indexOf(header) + 1 : -1;
    }
});
