// Global variables
window.pluginData = window.pluginData || [];
window.currentPage = window.currentPage || 1;
window.itemsPerPage = window.itemsPerPage || 12;
window.observer = window.observer || null;

window.formatDate = window.formatDate || new Intl.DateTimeFormat("default", { dateStyle: "medium" });
let lastFilterKey = "";

/**
 * Creates skeleton loading cards - Compact design
 */
function createSkeletonCards(count = 12) {
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < count; i++) {
        const card = document.createElement("div");
        card.className = "skeleton-card";
        card.innerHTML = `
            <div class="skeleton-card-header">
                <div class="skeleton skeleton-title"></div>
                <div class="skeleton skeleton-badge" style="width: 50px; height: 22px; border-radius: 6px;"></div>
            </div>
            <div class="skeleton-card-content">
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-text-short"></div>
                <div style="margin-top: 2px; padding: 8px 0; border-top: 1px solid rgba(0,0,0,0.06); border-bottom: 1px solid rgba(0,0,0,0.06); display: flex; gap: 10px;">
                    <div class="skeleton" style="width: 35%; height: 12px; border-radius: 6px;"></div>
                    <div class="skeleton" style="width: 40%; height: 12px; border-radius: 6px;"></div>
                </div>
                <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                    <div class="skeleton skeleton-badge"></div>
                    <div class="skeleton skeleton-badge"></div>
                    <div class="skeleton skeleton-badge"></div>
                </div>
            </div>
        `;
        fragment.appendChild(card);
    }
    return fragment;
}

/**
 * Fetch and display all plugins in the database view.
 */
async function showAllPlugins() {
    const container = document.getElementById("plugin-container");
    const categorySelect = document.getElementById("category");
    const sortSelect = document.getElementById("sort");

    if (!container || !categorySelect || !sortSelect) return;

    // Show skeleton loading
    container.innerHTML = "";
    container.appendChild(createSkeletonCards(window.itemsPerPage));

    await fetchPluginData();

    if (!window.pluginData.length) {
        container.innerHTML = "<p>❌ Unable to load plugins.</p>";
        return;
    }

    window.currentPage = 1;

    populateCategoryDropdown(window.pluginData);

    // Check if there's a filter category in sessionStorage (from clicking a category badge)
    const filterCategory = sessionStorage.getItem('filterCategory');
    if (filterCategory) {
        categorySelect.value = filterCategory;
        sessionStorage.removeItem('filterCategory'); // Clear it after using
    }

    // Setup clear search button
    setupClearSearchButton();
    setupRefreshButton();

    requestIdleCallback(() => renderPlugins(), { timeout: 300 });
}

/**
 * Populates category dropdown from plugins data
 */
function populateCategoryDropdown(plugins) {
    const categorySelect = document.getElementById("category");
    if (!categorySelect) return;

    const categories = new Set();
    let hasUncategorized = false;

    plugins.forEach(plugin => {
        if (plugin.categories.length > 0) {
            plugin.categories.forEach(cat => categories.add(cat));
        } else {
            hasUncategorized = true;
        }
    });

    // Keep "All Categories" option, add the rest
    const currentValue = categorySelect.value;
    categorySelect.innerHTML = '<option value="">All Categories</option>';

    [...categories].sort().forEach(cat => {
        const option = document.createElement("option");
        option.value = cat;
        option.textContent = cat;
        categorySelect.appendChild(option);
    });

    if (hasUncategorized) {
        const uncategorized = document.createElement("option");
        uncategorized.value = "__uncategorized__";
        uncategorized.textContent = "Uncategorized";
        categorySelect.appendChild(uncategorized);
    }

    // Restore previous value if it exists
    if (currentValue) {
        categorySelect.value = currentValue;
    }
}

/**
 * Setup clear search button functionality
 */
function setupClearSearchButton() {
    const searchInput = document.getElementById("search");
    const clearBtn = document.getElementById("clear-search");

    if (!searchInput || !clearBtn) return;

    searchInput.addEventListener("input", () => {
        if (searchInput.value.length > 0) {
            clearBtn.style.display = "flex";
        } else {
            clearBtn.style.display = "none";
        }
    });

    clearBtn.addEventListener("click", () => {
        searchInput.value = "";
        clearBtn.style.display = "none";
        window.currentPage = 1;
        renderPlugins();
    });
}

/**
 * Setup refresh button to bypass cached plugin data.
 */
function setupRefreshButton() {
    const refreshBtn = document.getElementById("refresh-data");
    const container = document.getElementById("plugin-container");
    const categorySelect = document.getElementById("category");
    if (!refreshBtn || !container || !categorySelect || refreshBtn.dataset.bound === "true") return;

    refreshBtn.dataset.bound = "true";
    refreshBtn.addEventListener("click", async () => {
        const refreshIcon = refreshBtn.querySelector(".refresh-icon");
        const refreshLabel = refreshBtn.querySelector(".refresh-label");
        const originalIcon = refreshIcon?.textContent || "↻";
        const originalLabel = refreshLabel?.textContent || "Refresh";
        const selectedCategory = categorySelect.value;

        refreshBtn.disabled = true;
        if (refreshIcon) refreshIcon.textContent = "…";
        if (refreshLabel) refreshLabel.textContent = "Refreshing";
        refreshBtn.setAttribute("aria-label", "Refreshing data");
        refreshBtn.setAttribute("title", "Refreshing data");
        container.innerHTML = "";
        container.appendChild(createSkeletonCards(window.itemsPerPage));

        await fetchPluginData(null, true);
        window.currentPage = 1;
        populateCategoryDropdown(window.pluginData);
        categorySelect.value = selectedCategory;
        lastFilterKey = "";
        renderPlugins();

        refreshBtn.disabled = false;
        if (refreshIcon) refreshIcon.textContent = originalIcon;
        if (refreshLabel) refreshLabel.textContent = originalLabel;
        refreshBtn.setAttribute("aria-label", "Refresh data");
        refreshBtn.setAttribute("title", "Refresh data");
    });
}

/**
 * Renders the plugin list with filtering, sorting, and lazy loading.
 */
function renderPlugins() {
    const container = document.getElementById("plugin-container");
    const categorySelect = document.getElementById("category");
    const sortSelect = document.getElementById("sort");
    const search = document.getElementById("search");

    if (!container || !categorySelect || !sortSelect) return;

    const query = search?.value?.toLowerCase() || "";
    const selectedCategory = categorySelect.value;
    const sortBy = sortSelect.value;

    const filterKey = `${selectedCategory}|${sortBy}|${query}|${window.currentPage}`;
    if (filterKey === lastFilterKey) return;
    lastFilterKey = filterKey;

    let filtered = window.pluginData.filter(plugin => {
        const manifest = plugin.manifest;

        const matchesCategory = selectedCategory
            ? selectedCategory === "__uncategorized__"
                ? plugin.categories.length === 0
                : plugin.categories.includes(selectedCategory)
            : true;

        const matchesSearch = [manifest.name, manifest.description, manifest.author]
            .filter(Boolean)
            .some(field => field.toLowerCase().includes(query));

        return matchesCategory && matchesSearch;
    });

    if (sortBy === "latest") {
        filtered.sort((a, b) => new Date(b.releases?.[0]?.published_at || 0) - new Date(a.releases?.[0]?.published_at || 0));
    } else if (sortBy === "name") {
        filtered.sort((a, b) => a.manifest.name.localeCompare(b.manifest.name));
    } else if (sortBy === "stars") {
        filtered.sort((a, b) => (b.stargazers_count || 0) - (a.stargazers_count || 0));
    } else if (sortBy === "forks") {
        filtered.sort((a, b) => (b.forks_count || 0) - (a.forks_count || 0));
    }

    // Update results count
    updateResultsInfo(filtered.length, window.pluginData.length, selectedCategory !== "", query);

    const start = (window.currentPage - 1) * window.itemsPerPage;
    const visible = filtered.slice(0, start + window.itemsPerPage);

    container.innerHTML = visible.length ? "" : "<p>No plugins found for this filter.</p>";

    const fragment = document.createDocumentFragment();
    visible.forEach(plugin => renderPluginCard(plugin, fragment));
    container.appendChild(fragment);
}

/**
 * Updates the results count display
 */
function updateResultsInfo(filteredCount, totalCount, hasCategoryFilter, query) {
    const resultsInfo = document.getElementById("results-info");
    if (!resultsInfo) return;

    if (filteredCount === totalCount) {
        resultsInfo.textContent = `Showing all ${totalCount} plugins`;
    } else {
        const filters = [];
        if (hasCategoryFilter) filters.push("category filter");
        if (query) filters.push("search");
        const filterText = filters.length ? ` (${filters.join(" + ")})` : "";
        resultsInfo.textContent = `${filteredCount} of ${totalCount} plugins${filterText}`;
    }
}

/**
 * Generates and appends a plugin card to the container.
 */
function renderPluginCard(plugin, container) {
    const manifest = plugin.manifest;
    const repoUrl = `https://github.com/${plugin.repository}`;
    const starCount = plugin.stargazers_count || 0;
    const forkCount = plugin.forks_count || 0;
    const releaseDate = plugin.releases?.[0]?.published_at
        ? formatDate.format(new Date(plugin.releases[0].published_at))
        : "Unknown";

    const card = document.createElement("div");
    card.className = "plugin-card";
    card.setAttribute("role", "button");
    card.tabIndex = 0;

    card.onclick = (e) => {
        // Don't open GitHub if clicking on a link or category badge
        if (!e.target.closest("a") && !e.target.closest(".clickable-category")) {
            window.open(repoUrl, "_blank");
        }
    };

    card.innerHTML = `
        <div class="plugin-card-header">
            <h2>${manifest.name}</h2>
            <span class="version-badge">v${manifest.version}</span>
        </div>
        <div class="plugin-card-content">
            <p class="plugin-description">${manifest.description}</p>
            <div class="plugin-metadata">
                <div class="plugin-metadata-item">
                    <strong>📅 Latest release:</strong> ${releaseDate}
                </div>
                <div class="plugin-metadata-item">
                    <strong>👤 Author:</strong> ${
                        manifest.author_uri
                            ? `<a href="${manifest.author_uri}" target="_blank" onclick="event.stopPropagation();">${manifest.author}</a>`
                            : manifest.author
                    }
                </div>
            </div>
            <div class="plugin-footer">
                ${
                    plugin.categories.length
                        ? plugin.categories.map(cat => `<span class="badge badge-category clickable-category" data-category="${cat}">${cat}</span>`).join(" ")
                        : `<span class="badge badge-uncategorized clickable-category" data-category="__uncategorized__">Uncategorized</span>`
                }
                ${starCount ? `<span class="badge badge-stars" title="${starCount} stars">⭐ ${starCount}</span>` : ""}
                ${forkCount ? `<span class="badge badge-forks" title="${forkCount} forks">🍴 ${forkCount}</span>` : ""}
            </div>
        </div>
    `;

    container.appendChild(card);
}

/**
 * Scroll handler voor lazy loading.
 */
function handleScroll() {
    const scrollY = window.scrollY + window.innerHeight;
    const docHeight = document.documentElement.scrollHeight;

    if (scrollY >= docHeight - 200) {
        window.currentPage++;
        renderPlugins();
    }
}

/**
 * Cleanup of event listeners when leaving the page.
 */
function cleanupEventListeners() {
    window.removeEventListener("scroll", handleScroll);
    if (window.observer) window.observer.disconnect();
}

/**
 * Handle category badge clicks - filter on the same page
 */
function handleCategoryClick(e) {
    const badge = e.target.closest('.clickable-category');
    if (!badge) return;

    const category = badge.dataset.category;
    if (!category) return;

    e.stopPropagation();

    // Update the category dropdown and re-render
    const categorySelect = document.getElementById("category");
    if (categorySelect) {
        categorySelect.value = category;
        window.currentPage = 1;
        renderPlugins();

        // Scroll to top of results
        document.getElementById("search-bar-container")?.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Init when navigating to the plugin page (via MkDocs).
 */
document$.subscribe(() => {
    if (!document.getElementById("plugin-container")) return;

    showAllPlugins();

    // Add event listener for category badge clicks
    document.addEventListener('click', handleCategoryClick);

    window.observer = new MutationObserver(() => {
        if (!document.getElementById("plugin-container")) {
            cleanupEventListeners();
        }
    });

    window.observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("scroll", handleScroll);
});

/**
 * Debounce function to limit how often a function can be called.
 * Useful for input events to prevent excessive re-renders.
 */
function debounce(fn, delay = 200) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn(...args), delay);
    };
}

/**
 * Filters or sorting options change → re-render.
 */
document.addEventListener("input", debounce((event) => {
    if (["sort", "category", "search"].includes(event.target.id)) {
        window.currentPage = 1;
        renderPlugins();
    }
}, 200));
