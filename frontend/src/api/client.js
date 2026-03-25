const API_BASE = "http://localhost:8000";

async function fetchJSON(path, params = {}) {
	const url = new URL(`${API_BASE}${path}`);
	Object.entries(params).forEach(([k, v]) => {
		if (v != null) url.searchParams.set(k, v);
	});

	const res = await fetch(url.toString());
	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		throw new Error(body.detail || `API error: ${res.status}`);
	}
	return res.json();
}

export function fetchHealth() {
	return fetchJSON("/health");
}

export function fetchTimeseries(subreddit, start, end, bucketSize = "6h") {
	return fetchJSON("/api/sentiment/timeseries", {
		subreddit,
		start,
		end,
		bucket_size: bucketSize,
	});
}

export function fetchCompare(subreddits, start, end) {
	return fetchJSON("/api/sentiment/compare", {
		subreddits: subreddits.join(","),
		start,
		end,
	});
}

export function fetchTopPosts(
	subreddit,
	start,
	end,
	limit = 20,
	sort = "score",
) {
	return fetchJSON("/api/posts/top", { subreddit, start, end, limit, sort });
}

export function fetchPostDetail(postId) {
	return fetchJSON(`/api/posts/${postId}`);
}

export function fetchSpikes(subreddit, lookbackHours = 24) {
	return fetchJSON("/api/spikes", {
		subreddit,
		lookback_hours: lookbackHours,
	});
}

export function fetchTerms(subreddit, start, end, limit = 50) {
	return fetchJSON("/api/posts/terms", { subreddit, start, end, limit });
}
