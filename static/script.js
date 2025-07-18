document.addEventListener("DOMContentLoaded", () => {
    const startCrawlBtn = document.getElementById("startCrawlBtn");
    const statusMessage = document.getElementById("statusMessage");
    const resultsOutput = document.getElementById("resultsOutput");

    startCrawlBtn.addEventListener("click", async () => {
        statusMessage.textContent = "크롤링 요청을 보냈습니다. 서버에서 데이터를 가져오는 중... (시간이 오래 걸릴 수 있습니다.)";
        resultsOutput.innerHTML = "<p>데이터를 처리 중입니다...</p>";
        startCrawlBtn.disabled = true; // 버튼 비활성화

        try {
            const response = await fetch("/crawl", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
            });

            const data = await response.json(); // 서버에서 모든 결과를 한 번에 받음

            if (data.status === "success" || data.status === "warning") {
                resultsOutput.innerHTML = ""; // 기존 내용 지우기

                const totalResults = data.results ? data.results.length : 0;
                let processedCount = 0;

                if (totalResults > 0) {
                    // 결과를 하나씩 순차적으로 표시 (시뮬레이션)
                    for (const item of data.results) {
                        processedCount++;
                        // 웹 페이지 상단에 진행 상황 업데이트
                        statusMessage.textContent = `현재 ${processedCount}/${totalResults} 번째 데이터를 가져오는 중입니다.`;

                        const div = document.createElement("div");
                        div.className = "result-item";
                        if (item.error) {
                            div.classList.add("error");
                        }
                        div.innerHTML = `
                            <p><strong>구단주명:</strong> ${item.구단주명}</p>
                            <p><strong>승:</strong> ${item.승}</p>
                            <p><strong>무:</strong> ${item.무}</p>
                            <p><strong>패:</strong> ${item.패}</p>
                            ${item.error ? `<p style="color:red;"><strong>오류:</strong> ${item.error}</p>` : ""}
                        `;
                        resultsOutput.appendChild(div);

                        // 각 결과 표시 사이에 약간의 딜레이를 주어 순차적인 느낌을 강화 (선택 사항)
                        await new Promise((resolve) => setTimeout(resolve, 100)); // 0.1초 대기
                    }
                } else {
                    resultsOutput.innerHTML = "<p>표시할 결과가 없습니다.</p>";
                }
                statusMessage.textContent = data.message; // 최종 요약 메시지 표시
            } else {
                statusMessage.textContent = `오류: ${data.message}`;
                resultsOutput.innerHTML = `<p style="color:red;">오류가 발생했습니다: ${data.message}</p>`;
                if (data.results && data.results.length > 0) {
                    // 부분적으로라도 성공한 데이터 표시
                    data.results.forEach((item) => {
                        const div = document.createElement("div");
                        div.className = "result-item error";
                        div.innerHTML = `
                            <p><strong>구단주명:</strong> ${item.구단주명}</p>
                            <p><strong>승:</strong> ${item.승}</p>
                            <p><strong>무:</strong> ${item.무}</p>
                            <p><strong>패:</strong> ${item.패}</p>
                            ${item.error ? `<p style="color:red;"><strong>오류:</strong> ${item.error}</p>` : ""}
                        `;
                        resultsOutput.appendChild(div);
                    });
                }
            }
        } catch (error) {
            statusMessage.textContent = `네트워크 오류 또는 서버 응답 실패: ${error}`;
            resultsOutput.innerHTML = `<p style="color:red;">크롤링 요청 중 문제가 발생했습니다: ${error}</p>`;
            console.error("Fetch error:", error);
        } finally {
            startCrawlBtn.disabled = false; // 버튼 다시 활성화
        }
    });
});
