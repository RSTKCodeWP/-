// How many plugins to show on the homepage
window.numberOfPlugins = window.numberOfPlugins || 6;
window.formatDate = window.formatDate || new Intl.DateTimeFormat("default", { dateStyle: "medium" });

/**
 * Creates skeleton loading cards - Compact design
 */
function createSkeletonCards(count = 6) {
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
                </div>
            </div>
        `;
        fragment.appendChild(card);
    }
    return fragment;
}

/**
 * Fetch and display the latest plugins on the homepage.
 */
async function showLatestPlugins() {
    const container = document.getElementById("plugin-container");
    if (!container) return;

    // Show skeleton loading
    container.innerHTML = "";
    container.appendChild(createSkeletonCards(window.numberOfPlugins));

    // Fallback op in-memory cache
    const plugins = window.pluginData?.length ? window.pluginData : await fetchPluginData();

    if (!plugins.length) {
        container.innerHTML = "<p>❌ Could not load latest plugins</p>";
        return;
    }

    updatePluginCountBadge(plugins.length);

    const latestPlugins = plugins
        .filter(p => p.releases?.[0]?.published_at)
        .sort((a, b) => new Date(b.releases[0].published_at) - new Date(a.releases[0].published_at))
        .slice(0, window.numberOfPlugins);

    const fragment = document.createDocumentFragment();
    latestPlugins.forEach(plugin => renderPluginCard(plugin, fragment));
    container.innerHTML = "";
    container.appendChild(fragment);
}

/**
 * Generate and append a plugin card to the container.
 */
function renderPluginCard(plugin, container) {
    const manifest = plugin.manifest;
    const repoUrl = `https://github.com/${plugin.repository}`;
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
            </div>
        </div>
    `;

    container.appendChild(card);
}

/**
 * Show the total number of plugins in the badge (optional).
 */
function updatePluginCountBadge(count) {
    const badge = document.getElementById("plugin-count");
    if (badge) {
        badge.textContent = `${count} Plugins Available`;
    }
}

/**
 * Handle category badge clicks - navigate to database with filter
 */
function handleCategoryClick(e) {
    const badge = e.target.closest('.clickable-category');
    if (!badge) return;

    const category = badge.dataset.category;
    if (!category) return;

    e.stopPropagation();

    // Store the category in sessionStorage for the database page to pick up
    sessionStorage.setItem('filterCategory', category);

    // Navigate to the database page using relative path from root
    // Get the base path (everything before the current page)
    const pathParts = window.location.pathname.split('/').filter(p => p);
    const baseDepth = pathParts.length - 1; // -1 for current page
    const relativePath = '../'.repeat(baseDepth > 0 ? baseDepth : 0) + 'database/';
    window.location.href = relativePath;
}

// Run when MkDocs Material loads a page
document$.subscribe(() => {
    if (document.getElementById("plugin-container")) {
        showLatestPlugins();

        // Add event listener for category badge clicks
        document.addEventListener('click', handleCategoryClick);
    }
});
