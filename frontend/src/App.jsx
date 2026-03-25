import { useCallback, useEffect, useState } from "react";
import { fetchTimeseries } from "./api/client";
import SpikeDetailPanel from "./components/SpikeDetailPanel";
import SubredditSelector from "./components/SubredditSelector";
import TimeRangePicker from "./components/TimeRangePicker";
import ViewTabs from "./components/ViewTabs";
import ComparisonView from "./views/ComparisonView";
import TimeSeriesView from "./views/TimeSeriesView";
import WordCloudView from "./views/WordCloudView";
import "./App.css";

function App() {
	const [subreddit, setSubreddit] = useState(null);
	const [timeRange, setTimeRange] = useState(() => {
		const now = Math.floor(Date.now() / 1000);
		return { start: now - 7 * 24 * 3600, end: now, label: "7d" };
	});
	const [activeView, setActiveView] = useState("trend");
	const [data, setData] = useState(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
	const [selectedSpike, setSelectedSpike] = useState(null);

	const loadData = useCallback(async () => {
		if (!subreddit) return;
		setLoading(true);
		setError(null);
		try {
			const result = await fetchTimeseries(
				subreddit,
				timeRange.start,
				timeRange.end,
			);
			setData(result);
		} catch (err) {
			setError(err.message);
			setData(null);
		} finally {
			setLoading(false);
		}
	}, [subreddit, timeRange]);

	useEffect(() => {
		loadData();
	}, [loadData]);

	return (
		<div className="app">
			<header className="app-header">
				<h1>Reddit Sentiment Analyzer</h1>
				<div className="controls">
					<SubredditSelector value={subreddit} onChange={setSubreddit} />
					<TimeRangePicker
						activeLabel={timeRange.label}
						onChange={(range) => setTimeRange(range)}
					/>
					<ViewTabs active={activeView} onChange={setActiveView} />
				</div>
			</header>
			<main>
				{activeView === "trend" && (
					<TimeSeriesView
						data={data}
						loading={loading}
						error={error}
						onSpikeClick={(bucket) => setSelectedSpike(bucket)}
					/>
				)}
				{activeView === "compare" && (
					<ComparisonView subreddit={subreddit} timeRange={timeRange} />
				)}
				{activeView === "wordcloud" && (
					<WordCloudView subreddit={subreddit} timeRange={timeRange} />
				)}
			</main>

			{selectedSpike && (
				<SpikeDetailPanel
					spike={selectedSpike}
					subreddit={subreddit}
					onClose={() => setSelectedSpike(null)}
				/>
			)}
		</div>
	);
}

export default App;
