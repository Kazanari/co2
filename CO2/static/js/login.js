document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    const response = await fetch("http://localhost:12345/login", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
    });

    if (response.ok) {
        window.location.href = "http://localhost:12345/data_visualization";
    } else {
        alert("ログイン失敗、ユーザ名とパスワードをチェックしてください。");
    }
});
