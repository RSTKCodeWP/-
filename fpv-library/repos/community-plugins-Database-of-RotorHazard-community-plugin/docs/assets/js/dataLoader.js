const PLUGIN_API_URL = "https://rhcp.hazardcreative.com/v1/plugin/data.json";
const CATEGORIES_API_URL = "https://rhcp.hazardcreative.com/v1/plugin/categories.json";
const CACHE_KEY = "pluginDataCache";
const CACHE_TS_KEY = "pluginDataCache_ts";
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minuten

/**
 * Fetches and combines plugin data with category mappings.
 */
async function fetchPluginData(onUpdate = null, forceRefresh = false) {
    const now = Date.now();
    const cachedRaw = localStorage.getItem(CACHE_KEY);
    const cachedTs = parseInt(localStorage.getItem(CACHE_TS_KEY), 10);

    const isFresh = cachedRaw && cachedTs && (now - cachedTs < CACHE_TTL_MS);

    if (!forceRefresh && isFresh) {
        try {
            const cached = JSON.parse(cachedRaw);
            window.pluginData = cached;
            if (typeof onUpdate === "function") onUpdate(cached);
            return cached;
        } catch (e) {
            console.warn("⚠️ Cache corrupted, refetching...", e);
        }
    }

    try {
        const [pluginJson, categoryJson] = await Promise.all([
            fetch(PLUGIN_API_URL).then(res => res.ok ? res.json() : Promise.reject(new Error(`Plugin fetch failed: ${res.status}`))),
            fetch(CATEGORIES_API_URL).then(res => res.ok ? res.json() : Promise.reject(new Error(`Category fetch failed: ${res.status}`))),
        ]);

        const repoToCategories = {};
        for (const [category, repos] of Object.entries(categoryJson)) {
            for (const repo of repos) {
                // Use lowercase as key for case-insensitive matching
                const repoLower = repo.toLowerCase();
                if (!repoToCategories[repoLower]) {
                    repoToCategories[repoLower] = [];
                }
                repoToCategories[repoLower].push(category);
            }
        }

        const plugins = Object.values(pluginJson).map(plugin => ({
            ...plugin,
            categories: repoToCategories[plugin.repository.toLowerCase()] || [],
        }));

        localStorage.setItem(CACHE_KEY, JSON.stringify(plugins));
        localStorage.setItem(CACHE_TS_KEY, now.toString());
        window.pluginData = plugins;
        if (typeof onUpdate === "function") onUpdate(plugins);
        return plugins;
    } catch (error) {
        console.error("❌ Failed to fetch plugin data:", error);

        // fallback: serve stale cache if possible
        if (cachedRaw) {
            try {
                const fallback = JSON.parse(cachedRaw);
                console.warn("⚠️ Using stale cache");
                window.pluginData = fallback;
                if (typeof onUpdate === "function") onUpdate(fallback);
                return fallback;
            } catch {
                // corrupted fallback
            }
        }

        window.pluginData = [];
        if (typeof onUpdate === "function") onUpdate([]);
        return [];
    }
}
