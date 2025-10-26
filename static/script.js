document.addEventListener("DOMContentLoaded", () => {
    const startCrawlBtn = document.getElementById("startCrawlBtn");
    const statusMessage = document.getElementById("statusMessage");
    const resultsOutput = document.getElementById("resultsOutput");

    if (startCrawlBtn) {
        startCrawlBtn.addEventListener("click", async () => {
            statusMessage.textContent = "크롤링 요청을 보냈습니다. 서버에서 데이터를 가져오는 중... (시간이 오래 걸릴 수 있습니다.)";
            resultsOutput.innerHTML = "<p>데이터를 처리 중입니다...</p>";
            startCrawlBtn.disabled = true;

            try {
                const response = await fetch("/crawl", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                });

                const data = await response.json();

                if (data.status === "success" || data.status === "warning") {
                    statusMessage.textContent = data.message + " 결과 페이지를 새 탭으로 엽니다.";
                    // 서버가 직접 HTML을 렌더링하고 파일을 생성하므로, localStorage는 더 이상 필요하지 않습니다.
                    window.open("/results_table", "_blank"); // 새 탭 열기
                    resultsOutput.innerHTML = "<p>크롤링이 완료되었습니다. 새 탭에서 결과를 확인하세요.</p>";
                } else {
                    statusMessage.textContent = `오류: ${data.message}`;
                    resultsOutput.innerHTML = `<p style="color:red;">오류가 발생했습니다: ${data.message}</p>`;
                }
            } catch (error) {
                statusMessage.textContent = `네트워크 오류 또는 서버 응답 실패: ${error}`;
                resultsOutput.innerHTML = `<p style="color:red;">크롤링 요청 중 문제가 발생했습니다: ${error}</p>`;
                console.error("Fetch error:", error);
            } finally {
                startCrawlBtn.disabled = false;
            }
        });
    }
});
