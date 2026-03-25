import { useCallback, useEffect, useState } from "react";
import {
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	ReferenceLine,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import { fetchCompare } from "../api/client";

const COLORS = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6"];

function formatTimestamp(ts) {
	return new Date(ts * 1000).toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

function mergeSeriesData(series) {
	if (!series?.length) return [];
	const map = new Map();
	for (const entry of series) {
		const sub = entry.subreddit;
		for (const b of entry.buckets) {
			if (!map.has(b.bucket_start)) {
				map.set(b.bucket_start, { bucket_start: b.bucket_start });
			}
			map.get(b.bucket_start)[sub] = b.avg_compound;
		}
	}
	return Array.from(map.values()).sort(
		(a, b) => a.bucket_start - b.bucket_start,
	);
}

export default function ComparisonView({ subreddit, timeRange }) {
	const [input, setInput] = useState("");
	const [subreddits, setSubreddits] = useState([]);
	const [data, setData] = useState(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);

	// Auto-populate input with current subreddit
	useEffect(() => {
		if (subreddit && !input) {
			setInput(subreddit);
		}
	}, [subreddit]);

	const loadComparison = useCallback(async () => {
		const names = input
			.split(",")
			.map((s) => s.trim())
			.filter(Boolean);
		if (names.length === 0) return;
		setSubreddits(names);
		setLoading(true);
		setError(null);
		try {
			const result = await fetchCompare(names, timeRange.start, timeRange.end);
			setData(result);
		} catch (err) {
			setError(err.message);
			setData(null);
		} finally {
			setLoading(false);
		}
	}, [input, timeRange]);

	const merged = data ? mergeSeriesData(data.series) : [];

	return (
		<div className="chart-container">
			<h2>Subreddit Comparison</h2>
			<div className="compare-input-row">
				<input
					type="text"
					className="compare-input"
					placeholder="e.g. nba, warriors, 49ers"
					value={input}
					onChange={(e) => setInput(e.target.value)}
					onKeyDown={(e) => e.key === "Enter" && loadComparison()}
				/>
				<button className="compare-button" onClick={loadComparison}>
					Compare
				</button>
			</div>

			{loading && (
				<div className="chart-placeholder">Loading comparison...</div>
			)}
			{error && <div className="chart-placeholder error">Error: {error}</div>}
			{!loading && !error && merged.length === 0 && (
				<div className="chart-placeholder">
					Enter subreddit names above and click Compare.
				</div>
			)}
			{!loading && merged.length > 0 && (
				<ResponsiveContainer width="100%" height={400}>
					<LineChart
						data={merged}
						margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
					>
						<CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
						<XAxis
							dataKey="bucket_start"
							tickFormatter={formatTimestamp}
							tick={{ fontSize: 11 }}
							interval="preserveStartEnd"
						/>
						<YAxis
							domain={[-1, 1]}
							tick={{ fontSize: 11 }}
							label={{
								value: "Compound Score",
								angle: -90,
								position: "insideLeft",
								offset: -5,
							}}
						/>
						<Tooltip
							labelFormatter={formatTimestamp}
							contentStyle={{
								background: "#1f2937",
								border: "1px solid #374151",
								borderRadius: 8,
								fontSize: 12,
							}}
						/>
						<Legend />
						<ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
						{subreddits.map((sub, i) => (
							<Line
								key={sub}
								type="monotone"
								dataKey={sub}
								name={`r/${sub}`}
								stroke={COLORS[i % COLORS.length]}
								strokeWidth={2}
								dot={false}
								connectNulls={false}
							/>
						))}
					</LineChart>
				</ResponsiveContainer>
			)}
		</div>
	);
}
