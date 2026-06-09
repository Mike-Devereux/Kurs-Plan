/** CSRF helper extracted from Chem-E supervisor tree editor. */
function webtoolGetCsrfToken() {
    const cookieValue = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="));
    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
}
