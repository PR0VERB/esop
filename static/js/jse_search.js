/**
 * JSE Company Autocomplete for company creation form.
 *
 * Searches the /api/v1/jse-companies/ endpoint with a 300ms debounce
 * and auto-fills form fields when a company is selected.
 */
(function () {
    "use strict";

    var searchInput = document.getElementById("jse-search");
    var resultsDiv = document.getElementById("jse-results");
    var selectedDiv = document.getElementById("jse-selected");
    var selectedBadge = document.getElementById("jse-selected-badge");
    var clearBtn = document.getElementById("jse-clear");
    var debounceTimer = null;

    if (!searchInput || !resultsDiv) return;

    var csrfToken = document.querySelector("[name=csrfmiddlewaretoken]");
    var csrfValue = csrfToken ? csrfToken.value : "";

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.appendChild(document.createTextNode(text || ""));
        return div.innerHTML;
    }

    searchInput.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        var q = this.value.trim();
        if (q.length < 2) {
            resultsDiv.classList.remove("active");
            resultsDiv.innerHTML = "";
            return;
        }
        debounceTimer = setTimeout(function () {
            fetch("/api/v1/jse-companies/?q=" + encodeURIComponent(q), {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (data) {
                    var results = data.results || data;
                    if (!results.length) {
                        resultsDiv.innerHTML =
                            '<div class="jse-result-item" style="color:#666;">No results found</div>';
                    } else {
                        resultsDiv.innerHTML = results
                            .map(function (c) {
                                return (
                                    '<div class="jse-result-item" data-id="' +
                                    c.id +
                                    '" data-ticker="' +
                                    escapeHtml(c.ticker) +
                                    '" data-name="' +
                                    escapeHtml(c.company_name) +
                                    '" data-isin="' +
                                    escapeHtml(c.isin) +
                                    '" data-sector="' +
                                    escapeHtml(c.sector) +
                                    '" data-regnum="' +
                                    escapeHtml(c.registration_number || "") +
                                    '"><span class="ticker">' +
                                    escapeHtml(c.ticker) +
                                    "</span> " +
                                    escapeHtml(c.company_name) +
                                    (c.sector
                                        ? '<br><span class="sector">' +
                                          escapeHtml(c.sector) +
                                          "</span>"
                                        : "") +
                                    "</div>"
                                );
                            })
                            .join("");
                    }
                    resultsDiv.classList.add("active");
                });
        }, 300);
    });

    // Selection handler (event delegation)
    resultsDiv.addEventListener("click", function (e) {
        var item = e.target.closest(".jse-result-item");
        if (!item || !item.dataset.ticker) return;

        var nameField = document.getElementById("id_name");
        var regField = document.getElementById("id_registration_number");
        var tickerField = document.getElementById("id_jse_ticker");
        var isinField = document.getElementById("id_jse_isin");
        var sectorField = document.getElementById("id_sector");

        if (nameField && !nameField.value) nameField.value = item.dataset.name;
        if (tickerField) tickerField.value = item.dataset.ticker;
        if (isinField) isinField.value = item.dataset.isin;
        if (sectorField && !sectorField.value)
            sectorField.value = item.dataset.sector;
        if (regField && !regField.value && item.dataset.regnum)
            regField.value = item.dataset.regnum;

        // Show selection badge
        if (selectedBadge && selectedDiv) {
            selectedBadge.textContent =
                item.dataset.ticker + " \u2013 " + item.dataset.name;
            selectedDiv.style.display = "block";
        }

        // Trigger background enrichment
        if (item.dataset.id && csrfValue) {
            fetch(
                "/api/v1/jse-companies/" + item.dataset.id + "/enrich/",
                {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfValue,
                        "Content-Type": "application/json",
                    },
                    credentials: "same-origin",
                }
            );
        }

        resultsDiv.classList.remove("active");
        searchInput.value = "";
    });

    // Clear selection
    if (clearBtn) {
        clearBtn.addEventListener("click", function () {
            var tickerField = document.getElementById("id_jse_ticker");
            var isinField = document.getElementById("id_jse_isin");
            if (tickerField) tickerField.value = "";
            if (isinField) isinField.value = "";
            if (selectedDiv) selectedDiv.style.display = "none";
        });
    }

    // Close dropdown on click outside
    document.addEventListener("click", function (e) {
        if (!e.target.closest(".jse-search-wrapper")) {
            resultsDiv.classList.remove("active");
        }
    });

    // Keyboard navigation
    searchInput.addEventListener("keydown", function (e) {
        var items = resultsDiv.querySelectorAll(
            ".jse-result-item[data-ticker]"
        );
        var current = resultsDiv.querySelector(".jse-result-item.selected");
        var index = -1;

        if (current) {
            for (var i = 0; i < items.length; i++) {
                if (items[i] === current) {
                    index = i;
                    break;
                }
            }
        }

        if (e.key === "ArrowDown") {
            e.preventDefault();
            if (current) current.classList.remove("selected");
            index = (index + 1) % items.length;
            if (items[index]) items[index].classList.add("selected");
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            if (current) current.classList.remove("selected");
            index = index <= 0 ? items.length - 1 : index - 1;
            if (items[index]) items[index].classList.add("selected");
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (current) current.click();
        } else if (e.key === "Escape") {
            resultsDiv.classList.remove("active");
        }
    });
})();
