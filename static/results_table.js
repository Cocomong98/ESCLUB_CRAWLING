document.addEventListener("DOMContentLoaded", () => {
    const resultsTableBody = document.querySelector("#resultsTable tbody");
    const lastUpdatedInfo = document.getElementById("lastUpdatedInfo"); // 최신화 날짜 표시할 요소

    const storedResults = localStorage.getItem("fconline_crawl_results");
    const lastUpdatedTimestamp = localStorage.getItem("fconline_last_updated"); // 최신화 날짜 가져오기

    if (storedResults) {
        let results = JSON.parse(storedResults);

        // -------------------------------------------------------------
        // 채굴 효율 높은 순으로 정렬
        results.sort((a, b) => {
            const efficiencyA = typeof a["채굴 효율"] === "number" ? a["채굴 효율"] : -Infinity; // N/A는 가장 뒤로
            const efficiencyB = typeof b["채굴 효율"] === "number" ? b["채굴 효율"] : -Infinity;
            return efficiencyB - efficiencyA; // 내림차순 정렬 (높은 값이 먼저)
        });
        // -------------------------------------------------------------

        let successCount = 0;
        let failCount = 0;

        resultsTableBody.innerHTML = ""; // 기존 내용 초기화

        if (results.length > 0) {
            results.forEach((item, index) => {
                // index를 사용하여 순위 부여
                const row = document.createElement("tr");
                let rowClass = "";
                if (item.error) {
                    rowClass = "error-row";
                    failCount++;
                } else {
                    successCount++;
                }
                row.className = rowClass;

                row.innerHTML = `
                    <td>${index + 1}</td> <td>${item.구단주명 || "N/A"}</td>
                    <td>${item.승}</td>
                    <td>${item.무}</td>
                    <td>${item.패}</td>
                    <td>${item.판수}</td>
                    <td>${item["채굴 효율"]}</td>
                    <td>${item["승률"]}</td>
                    <td><a href="${item.URL}" target="_blank" title="${item.URL}">${item.URL ? "링크" : "N/A"}</a></td>
                    <td>${item.error || "성공"}</td>
                `;
                resultsTableBody.appendChild(row);
            });

            // summaryMessage 대신 최신화 날짜 표시
            if (lastUpdatedTimestamp) {
                lastUpdatedInfo.textContent = `마지막 최신화: ${lastUpdatedTimestamp}`;
            } else {
                lastUpdatedInfo.textContent = `마지막 최신화: 정보 없음`;
            }
        } else {
            resultsTableBody.innerHTML = '<tr><td colspan="10">표시할 결과가 없습니다.</td></tr>'; // colspan 조정
            lastUpdatedInfo.textContent = "크롤링된 데이터가 없습니다.";
        }

        // localStorage 비우기는 여기서 하지 않는 것이 좋습니다.
        // 사용자가 새 탭을 다시 열 때도 데이터를 볼 수 있어야 하므로.
    } else {
        resultsTableBody.innerHTML = '<tr><td colspan="10">표시할 데이터가 없습니다. 메인 페이지에서 크롤링을 시작해주세요.</td></tr>'; // colspan 조정
        lastUpdatedInfo.textContent = "크롤링된 데이터가 localStorage에 없습니다. 메인 페이지에서 크롤링을 시작해주세요.";
    }
});
