import {
	CartesianGrid,
	Line,
	LineChart,
	ReferenceLine,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";

function formatTimestamp(ts) {
	const d = new Date(ts * 1000);
	return d.toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

function CustomDot({ cx, cy, payload, onSpikeClick }) {
	if (payload.spike_flag) {
		return (
			<circle
				cx={cx}
				cy={cy}
				r={6}
				fill="#ef4444"
				stroke="#fff"
				strokeWidth={2}
				style={{ cursor: "pointer" }}
				onClick={(e) => {
					e.stopPropagation();
					onSpikeClick?.(payload);
				}}
			/>
		);
	}
	return <circle cx={cx} cy={cy} r={3} fill="#3b82f6" />;
}

function CustomTooltip({ active, payload }) {
	if (!active || !payload?.length) return null;
	const d = payload[0].payload;
	return (
		<div className="tooltip">
			<p className="tooltip-time">{formatTimestamp(d.bucket_start)}</p>
			<p>
				Compound: <strong>{d.avg_compound?.toFixed(3) ?? "N/A"}</strong>
			</p>
			<p>
				Posts: {d.post_count} &middot; Comments: {d.comment_count}
			</p>
			<p>Avg upvote ratio: {d.avg_upvote_ratio?.toFixed(2) ?? "N/A"}</p>
			{d.spike_flag && (
				<p className="spike-label">Click to investigate spike</p>
			)}
		</div>
	);
}

export default function TimeSeriesView({ data, loading, error, onSpikeClick }) {
	if (loading) {
		return <div className="chart-placeholder">Loading sentiment data...</div>;
	}

	if (error) {
		return <div className="chart-placeholder error">Error: {error}</div>;
	}

	if (!data?.buckets?.length) {
		return (
			<div className="chart-placeholder">
				No sentiment data available for this range.
			</div>
		);
	}

	return (
		<div className="chart-container">
			<h2>Sentiment Trend &mdash; r/{data.subreddit}</h2>
			<ResponsiveContainer width="100%" height={400}>
				<LineChart
					data={data.buckets}
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
					<Tooltip content={<CustomTooltip />} />
					<ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
					<Line
						type="monotone"
						dataKey="avg_compound"
						stroke="#3b82f6"
						strokeWidth={2}
						dot={<CustomDot onSpikeClick={onSpikeClick} />}
						connectNulls={false}
						activeDot={{ r: 6, fill: "#2563eb" }}
					/>
				</LineChart>
			</ResponsiveContainer>
		</div>
	);
}
