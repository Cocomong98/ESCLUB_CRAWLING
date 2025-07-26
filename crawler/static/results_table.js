document.addEventListener("DOMContentLoaded", () => {
    const league1TableBody = document.querySelector("#league1Table tbody");
    const league2TableBody = document.querySelector("#league2Table tbody");
    const league1SummaryMessage = document.getElementById("league1_summary_message");
    const league2SummaryMessage = document.getElementById("league2_summary_message");
    const lastUpdatedInfo = document.getElementById("lastUpdatedInfo");

    const storedResults = localStorage.getItem("fconline_crawl_results");
    const lastUpdatedTimestamp = localStorage.getItem("fconline_last_updated");

    if (storedResults) {
        let allResults = JSON.parse(storedResults);

        // 헬퍼 함수: 데이터 분류 및 정렬, 테이블 생성
        function renderTable(targetTableBody, leagueData, leagueSummaryElem, leagueName) {
            targetTableBody.innerHTML = ""; // 기존 내용 초기화

            if (leagueData.length > 0) {
                // 채굴 효율 높은 순으로 정렬
                leagueData.sort((a, b) => {
                    const efficiencyA = typeof a["채굴 효율"] === "number" ? a["채굴 효율"] : -Infinity;
                    const efficiencyB = typeof b["채굴 효율"] === "number" ? b["채굴 효율"] : -Infinity;
                    return efficiencyB - efficiencyA; // 내림차순 정렬
                });

                let successCount = 0;
                let failCount = 0;

                leagueData.forEach((item, index) => {
                    const row = document.createElement("tr");
                    let rowClass = "";
                    if (item.error) {
                        rowClass = "error-row";
                        failCount++;
                    } else {
                        successCount++;
                    }
                    row.className = rowClass;

                    // -------------------------------------------------------------
                    // '비고' 값에 따른 CSS 클래스 결정
                    let remarkClass = "";
                    let remarkText = item.비고 || "-"; // 비고 필드가 없으면 '-'
                    if (remarkText.startsWith("↑")) {
                        remarkClass = "rank-up";
                    } else if (remarkText.startsWith("↓")) {
                        remarkClass = "rank-down";
                    } else if (remarkText === "-") {
                        remarkClass = "rank-no-change";
                    } else if (remarkText === "New") {
                        remarkClass = "rank-up"; // 새로운 플레이어도 빨간색
                    } else if (remarkText === "오류") {
                        remarkClass = "error-row"; // 오류가 나면 오류 스타일
                    }

                    row.innerHTML = `
                        <td>${index + 1}</td> <td class="${remarkClass}">${remarkText}</td> <td>${item.구단주명 || "N/A"}</td>
                        <td>${item.판수}</td>
                        <td>${item.승}</td>
                        <td>${item.무}</td>
                        <td>${item.패}</td>
                        <td>${item["채굴 효율"]}</td>
                        <td>${item["승률"]}</td>
                        <td><a href="${item.URL}" target="_blank" title="${item.URL}">${item.URL ? "링크" : "N/A"}</a></td>
                        <td>${item.error || "성공"}</td>
                    `;
                    // -------------------------------------------------------------
                    targetTableBody.appendChild(row);
                });
                leagueSummaryElem.textContent = `${leagueName} : 총 ${leagueData.length}개 중 ${successCount}개 성공, ${failCount}개 실패.`;
            } else {
                targetTableBody.innerHTML = '<tr><td colspan="11">표시할 결과가 없습니다.</td></tr>'; // colspan 조정
                leagueSummaryElem.textContent = `${leagueName} : 크롤링된 데이터가 없습니다.`;
            }
        }

        // 데이터 필터링
        const league1Results = allResults.filter((item) => item.리그명 === "1부리그");
        const league2Results = allResults.filter((item) => item.리그명 === "2부리그");

        // 각 리그 테이블 렌더링
        renderTable(league1TableBody, league1Results, league1SummaryMessage, "1부리그");
        renderTable(league2TableBody, league2Results, league2SummaryMessage, "2부리그");

        // 최종 최신화 날짜 표시
        if (lastUpdatedTimestamp) {
            lastUpdatedInfo.textContent = `데이터 마지막 최신화: ${lastUpdatedTimestamp}`;
        } else {
            lastUpdatedInfo.textContent = `데이터 마지막 최신화: 정보 없음`;
        }
    } else {
        league1TableBody.innerHTML = '<tr><td colspan="11">표시할 데이터가 없습니다. 메인 페이지에서 크롤링을 시작해주세요.</td></tr>'; // colspan 조정
        league2TableBody.innerHTML = '<tr><td colspan="11">표시할 데이터가 없습니다. 메인 페이지에서 크롤링을 시작해주세요.</td></tr>'; // colspan 조정
        lastUpdatedInfo.textContent = "크롤링된 데이터가 localStorage에 없습니다. 메인 페이지에서 크롤링을 시작해주세요.";
    }
});
